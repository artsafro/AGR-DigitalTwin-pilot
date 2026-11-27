-- ID-colour review copy (moskovsky-sosh1200): every mesh gets one Multi/Sub "MS_REVIEW_ID" whose slots keep the
-- material IDs and cover names of the scene's own Multi/Sub but carry flat primitive colours, no maps, so the user
-- sees the ID split. Review only, never the delivery. Paths by env: REVIEW_IN, REVIEW_OUT (batch cuts "C:" args).
-- usage: 3dsmaxbatch.exe review_idcolor_max.ms
(
    local src = systemTools.getEnvVariable "REVIEW_IN"
    local dst = systemTools.getEnvVariable "REVIEW_OUT"
    loadMaxFile src useFileUnits:true quiet:true
    local palette = #((color 70 70 75), (color 225 205 160), (color 190 60 45), (color 40 200 110), (color 110 175 70),
                      (color 160 220 90), (color 30 110 50), (color 150 90 200), (color 230 140 40), (color 60 160 200),
                      (color 230 60 160), (color 240 230 60), (color 120 120 220), (color 200 200 200), (color 90 50 30))
    local ids = #(); local names = #()
    for o in geometry where o.material != undefined do
    (
        local m = o.material
        if classOf m == MultiMaterial then
            for i = 1 to m.numsubs do
                if findItem ids m.materialIDList[i] == 0 do
                (
                    append ids m.materialIDList[i]
                    append names (if m.materialList[i] != undefined then m.materialList[i].name else m.names[i])
                )
        else if findItem ids 1 == 0 do (append ids 1; append names m.name)
    )
    local ms = MultiMaterial numsubs:ids.count name:"MS_REVIEW_ID"
    for i = 1 to ids.count do
    (
        ms.materialIDList[i] = ids[i]
        ms.names[i] = names[i]
        local s = StandardMaterial name:(formattedPrint ids[i] format:"02d" + "_" + names[i])
        s.diffuse = palette[1 + mod (i - 1) palette.count]
        s.ambient = s.diffuse
        s.showInViewport = true
        ms.materialList[i] = s
        format "ID % -> % %\n" ids[i] names[i] s.diffuse
    )
    for o in geometry where o.material != undefined do o.material = ms
    saveMaxFile dst quiet:true
    format "saved %\n" dst
)
