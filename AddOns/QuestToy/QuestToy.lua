
local LibSerpix = LibStub("LibSerpix-0.1")
local frame = CreateFrame("Frame")


frame:RegisterEvent("QUEST_ACCEPTED")
frame:RegisterEvent("QUEST_COMPLETE")
frame:RegisterEvent("COMBAT_LOG_EVENT_UNFILTERED")

frame:SetScript("OnEvent", function(self, event, ...)

    if event == "QUEST_ACCEPTED" then 
        local questLogIndex, questID = ...

        local description, objectives =
            GetQuestLogQuestText(questLogIndex)

        LibSerpix.add_data("퀘스트 수락내용", {
            -- questID = questID,
            description = description or "",
            objectives = objectives or "",
        })

        print("퀘스트 수락내용 전송완료:", description)

    elseif event == "QUEST_COMPLETE" then
        local progress =
            GetRewardText() 
        
        LibSerpix.add_data("퀘스트 완료내용", {
            progress = progress or "",
        })

        print("퀘스트 완료내용 전송완료", progress or "")



    elseif event == "COMBAT_LOG_EVENT_UNFILTERED" then
    local info = { CombatLogGetCurrentEventInfo() }

    local subevent = info[2]
    local sourceGUID = info[4]
    local destGUID = info[8]

        -- 내가 가한 피해만 처리
        if sourceGUID == UnitGUID("player") then
            local damage
            local spellID
            local spellName
            local critical
            local sourceName = info[5]
            local destName = info[9]

            if subevent == "SWING_DAMAGE" then
                -- 일반 근접 공격
                damage = info[12]
                critical = info[18]

            elseif subevent == "SPELL_DAMAGE"
                or subevent == "RANGE_DAMAGE" then
                -- 주문 또는 원거리 공격
                spellID = info[12]
                spellName = info[13]
                damage = info[15]
                critical = info[21]
            end

            if critical then
                LibSerpix.add_data("치명타", {
                    targetName = destName or "",
                    spellID = spellID or 0,
                    spellName = spellName or "일반 공격",
                    damage = damage or 0,
                })

                print("[치명타]", spellName or "일반 공격", damage)
            end
        end
end
end)
