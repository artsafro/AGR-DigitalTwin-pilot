-- Own implementation. Category actions can be assigned to any Max toolbar.
macroScript AGRToolsXView category:"AGR Tools" tooltip:"xView check" buttonText:"xView check"
(on execute do python.Execute "agr_tools_runtime.ui('xview')")
macroScript AGRToolsCleanup category:"AGR Tools" tooltip:"Pre-export clean-up (dry-run)" buttonText:"Pre-export clean-up"
(on execute do python.Execute "agr_tools_runtime.ui('cleanup')")
macroScript AGRToolsMatID category:"AGR Tools" tooltip:"MatID check" buttonText:"MatID check"
(on execute do python.Execute "agr_tools_runtime.ui('matid')")
macroScript AGRToolsNudge category:"AGR Tools" tooltip:"UV integer-tile nudge (dry-run)" buttonText:"UV nudge"
(on execute do python.Execute "agr_tools_runtime.ui('nudge')")
macroScript AGRToolsNudgeApply category:"AGR Tools" tooltip:"Apply UV nudge to new export copies" buttonText:"Apply UV nudge"
(on execute do python.Execute "agr_tools_runtime.ui('nudge_apply')")
macroScript AGRToolsAtlas category:"AGR Tools" tooltip:"UDIM -> NPM atlas (dry-run)" buttonText:"UDIM to NPM atlas"
(on execute do python.Execute "agr_tools_runtime.ui('atlas')")
macroScript AGRToolsAtlasApply category:"AGR Tools" tooltip:"Apply NPM atlas to new export copies" buttonText:"Apply NPM atlas"
(on execute do python.Execute "agr_tools_runtime.ui('atlas_apply')")
macroScript AGRToolsUcx category:"AGR Tools" tooltip:"UCX collision (dry-run)" buttonText:"UCX collision"
(on execute do python.Execute "agr_tools_runtime.ui('ucx')")
macroScript AGRToolsUcxApply category:"AGR Tools" tooltip:"Apply UCX to new export copies" buttonText:"Apply UCX"
(on execute do python.Execute "agr_tools_runtime.ui('ucx_apply')")
macroScript AGRToolsTexel category:"AGR Tools" tooltip:"Texel readout" buttonText:"Texel readout"
(on execute do python.Execute "agr_tools_runtime.ui('texel')")
macroScript AGRToolsOpen category:"AGR Tools" tooltip:"AGR Tools" buttonText:"AGR Tools"
(
    on execute do (
        global AGRToolsDialog
        try (destroyDialog AGRToolsDialog) catch ()
        rollout AGRToolsDialog "AGR Tools" width:360 (
            button xv "xView check" width:340
            button dry "Pre-export clean-up (dry-run)" width:340
            button applyCopy "Apply preview to new export copies" width:340
            button mid "MatID check" width:340
            button nudge "UV integer-tile nudge (dry-run)" width:340
            button nudgeApply "Apply UV nudge to new export copies" width:340
            button atlas "UDIM -> NPM atlas (dry-run)" width:340
            button atlasApply "Apply NPM atlas to new export copies" width:340
            button ucx "UCX collision (dry-run)" width:340
            button ucxApply "Apply UCX to new export copies" width:340
            button texel "Texel readout" width:340
            label info "JSON report in Listener; checks select offenders."
            on xv pressed do python.Execute "agr_tools_runtime.ui('xview')"
            on dry pressed do python.Execute "agr_tools_runtime.ui('cleanup')"
            on applyCopy pressed do python.Execute "agr_tools_runtime.ui('apply')"
            on mid pressed do python.Execute "agr_tools_runtime.ui('matid')"
            on nudge pressed do python.Execute "agr_tools_runtime.ui('nudge')"
            on nudgeApply pressed do python.Execute "agr_tools_runtime.ui('nudge_apply')"
            on atlas pressed do python.Execute "agr_tools_runtime.ui('atlas')"
            on atlasApply pressed do python.Execute "agr_tools_runtime.ui('atlas_apply')"
            on ucx pressed do python.Execute "agr_tools_runtime.ui('ucx')"
            on ucxApply pressed do python.Execute "agr_tools_runtime.ui('ucx_apply')"
            on texel pressed do python.Execute "agr_tools_runtime.ui('texel')"
        )
        createDialog AGRToolsDialog
    )
)

