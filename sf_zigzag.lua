-- sf_zigzag.lua
-- Расчет канонического ЗигЗага по отклонению (deviation) в процентах

function CalculateZigzag(high, low, dev_percent)
    if not high or not low or #high < 2 or #low < 2 then
        return 0, 0, 0, 0, 0, {}
    end

    local dev_frac  = dev_percent / 100
    local trendDir  = 0
    local lineStart = 0
    local lineEnd   = 0
    local startBar  = 1
    local endBar    = 0

    -- ========================================================================
    -- 1. Первичный поиск импульса: отслеживаем экстремумы до первого deviation
    -- ========================================================================
    local maxVal = high[1]
    local maxBar = 1
    local minVal = low[1]
    local minBar = 1

    for i = 2, #high do
        if high[i] > maxVal then maxVal, maxBar = high[i], i end
        if low[i]  < minVal then minVal, minBar = low[i],  i end

        local dev_val = minVal * dev_frac
        if maxVal - minVal >= dev_val and maxBar ~= minBar then
            trendDir  = (maxBar > minBar) and 1 or -1
            lineStart = (trendDir == 1) and minVal or maxVal
            startBar  = (trendDir == 1) and minBar or maxBar
            lineEnd   = (trendDir == 1) and maxVal or minVal
            endBar    = (trendDir == 1) and maxBar or minBar
            break
        end
    end

    if trendDir == 0 then
        return 0, 0, 0, 0, 0, {}
    end

    -- ========================================================================
    -- 2. Продолжение ЗигЗага по следующим свечам (от endBar + 1 до конца)
    -- ========================================================================
    local allPivots = {}

    local p1 = {}
    p1.bar   = startBar
    p1.price = lineStart
    p1.type  = (trendDir == 1 and "LOW" or "HIGH")
    allPivots[1] = p1

    local p2 = {}
    p2.bar   = endBar
    p2.price = lineEnd
    p2.type  = (trendDir == 1 and "HIGH" or "LOW")
    allPivots[2] = p2

    for k = endBar + 1, #high do
        local h = high[k]
        local l = low[k]

        if trendDir == 1 then
            -- Тянем вершину выше, если цена растет
            if h >= lineEnd then
                lineEnd = h
                endBar  = k
                allPivots[#allPivots].bar   = endBar
                allPivots[#allPivots].price = lineEnd

            -- Откат от вершины на >= deviation: разворот тренда вниз
            elseif l <= lineEnd - lineEnd * dev_frac then
                trendDir  = -1
                lineStart = lineEnd
                startBar  = endBar
                lineEnd   = l
                endBar    = k

                local pNew = {}
                pNew.bar   = endBar
                pNew.price = lineEnd
                pNew.type  = "LOW"
                allPivots[#allPivots + 1] = pNew
            end

        elseif trendDir == -1 then
            -- Тянем дно ниже, если цена падает
            if l <= lineEnd then
                lineEnd = l
                endBar  = k
                allPivots[#allPivots].bar   = endBar
                allPivots[#allPivots].price = lineEnd

            -- Отскок от дна на >= deviation: разворот тренда вверх
            elseif h >= lineEnd + lineEnd * dev_frac then
                trendDir  = 1
                lineStart = lineEnd
                startBar  = endBar
                lineEnd   = h
                endBar    = k

                local pNew = {}
                pNew.bar   = endBar
                pNew.price = lineEnd
                pNew.type  = "HIGH"
                allPivots[#allPivots + 1] = pNew
            end
        end
    end

    return trendDir, lineStart, startBar, lineEnd, endBar, allPivots
end

CalculateFirstLine = CalculateZigzag
