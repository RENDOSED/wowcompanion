local LibSerpix = LibStub("LibSerpix-0.1")

-- LibSerpix는 OnUpdate 함수를 만들어 두기만 하고 어떤 프레임에도 연결하지 않는다.
-- 그래서 직접 연결해 주어야 데이터 픽셀이 칠해진다.
-- (SetScript는 이 파일이 로드되는 시점의 함수를 붙잡으므로, 나중에 다른 애드온이 같은 이름을 덮어써도 영향이 없다)
LibSerpix.serializer.vals.u = LibSerpix.serializer.vals.u or {}
local driver = CreateFrame("Frame")
driver:SetScript("OnUpdate", _G.OnUpdate)

-- 2초마다 테스트 메시지 전송
-- local count = 0
-- C_Timer.NewTicker(2, function()
--     count = count + 1
--     LibSerpix.add_data("rumble", { msg = "hello", n = count, t = time() })
--     print("RumbleSerpix 전송 #" .. count)
-- end)