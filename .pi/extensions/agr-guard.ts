/** Project-owned, headless PreToolUse bridge. No hook rules live here. */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const adapter = fileURLToPath(new URL("../../tools/hooks/pi_guard_adapter.py", import.meta.url));
const guarded = new Set(["bash", "powershell", "edit", "write"]);

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (!guarded.has(event.toolName)) return;
    try {
      const output = await new Promise<string>((resolve, reject) => {
        const child = spawn("py", ["-3", adapter], {
          cwd: ctx.cwd, windowsHide: true, stdio: ["pipe", "pipe", "pipe"],
        });
        let stdout = "";
        let stderr = "";
        const timer = setTimeout(() => {
          child.kill();
          reject(new Error("adapter timed out"));
        }, 25000);
        child.on("error", (error) => { clearTimeout(timer); reject(error); });
        child.stdin.on("error", (error) => { clearTimeout(timer); reject(error); });
        child.stdout.setEncoding("utf8").on("data", (text) => { stdout += text; });
        child.stderr.setEncoding("utf8").on("data", (text) => { stderr += text; });
        child.on("close", (code) => {
          clearTimeout(timer);
          if (code !== 0) reject(new Error(`adapter exited ${code}: ${stderr.trim()}`));
          else resolve(stdout);
        });
        child.stdin.end(JSON.stringify({tool: event.toolName, input: event.input, cwd: ctx.cwd}));
      });
      const result = JSON.parse(output);
      if (result.decision === "allow" && typeof result.reason === "string") return;
      if (result.decision === "block" && typeof result.reason === "string" && result.reason)
        return {block: true, reason: result.reason};
      throw new Error("invalid adapter decision");
    } catch (error) {
      return {block: true, reason: `Pi guard failed: ${String(error)}`};
    }
  });
}
