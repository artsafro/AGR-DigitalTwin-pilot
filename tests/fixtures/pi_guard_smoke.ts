/** Explicit smoke-test driver only; never auto-loaded as a project extension. */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "agr_guard_smoke", label: "AGR guard smoke",
    description: "Run the approved guard smoke: git status, then a guarded reset submission. No edits.",
    parameters: {type: "object", properties: {}, required: []} as any,
    async execute(_id, _args, _signal, _update, ctx) {
      const status = await ctx.executeTool("bash", {command: "git status"});
      if (status.isError) throw new Error(`status failed: ${JSON.stringify(status)}`);
      const reset = await ctx.executeTool("bash", {command: "git reset --hard HEAD"});
      const text = JSON.stringify({status, reset});
      if (!reset.isError || !text.includes("guard.py: git reset --hard discards work"))
        throw new Error(`reset was not guard-blocked: ${text}`);
      return {content: [{type: "text", text}], details: {}};
    },
  });
}
