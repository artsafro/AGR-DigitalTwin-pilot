-- Own implementation. Category actions can be assigned to any Max toolbar.
macroScript AGRToolsXView category:"AGR Tools" tooltip:"xView check" buttonText:"xView check"
(on execute do python.Execute "agr_tools_runtime.ui('xview')")
macroScript AGRToolsCleanup category:"AGR Tools" tooltip:"Pre-export clean-up (dry-run)" buttonText:"Pre-export clean-up"
(on execute do python.Execute "agr_tools_runtime.ui('cleanup')")
macroScript AGRToolsMatID category:"AGR Tools" tooltip:"MatID check" buttonText:"MatID check"
(on execute do python.Execute "agr_tools_runtime.ui('matid')")
macroScript AGRToolsOpen category:"AGR Tools" tooltip:"AGR Tools" buttonText:"AGR Tools"
(
    on execute do (
        global AGRToolsDialog
        try (destroyDialog AGRToolsDialog) catch ()
        rollout AGRToolsDialog "AGR Tools" width:310 (
            button xv "xView check" width:290
            button dry "Pre-export clean-up (dry-run)" width:290
            button applyCopy "Apply preview to new export copies" width:290
            button mid "MatID check" width:290
            label info "JSON report in Listener; checks select offenders."
            on xv pressed do python.Execute "agr_tools_runtime.ui('xview')"
            on dry pressed do python.Execute "agr_tools_runtime.ui('cleanup')"
            on applyCopy pressed do python.Execute "agr_tools_runtime.ui('apply')"
            on mid pressed do python.Execute "agr_tools_runtime.ui('matid')"
        )
        createDialog AGRToolsDialog
    )
)

