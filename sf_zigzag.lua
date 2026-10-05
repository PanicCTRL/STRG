-- sf_zigzag.lua
-- Расчет канонического ЗигЗага по отклонению (deviation) в процентах

function CalculateZigzag(high, low, dev_percent)
    if not high or not low or #high < 2 or #low < 2 then
        return 0, 0, 0, 0, 0, {}
    end

    local dev_frac  = dev_percent / 100
    local dev_val   = low[1] * dev_frac
    local trendDir  = 0
    local lineStart = 0
    local lineEnd   = 0
    local startBar  = 1
    local endBar    = 0

    -- ========================================================================
    -- 1. Первичный поиск импульса от открытия дня
    -- ========================================================================
    for i = 2, #high do
        if high[i] - low[1] >= dev_val then
            trendDir, lineStart, lineEnd, endBar = 1, low[1], high[i], i
            break
        elseif high[1] - low[i] >= dev_val then
            trendDir, lineStart, lineEnd, endBar = -1, high[1], low[i], i
            break
        end
    end

    if trendDir == 0 then
        return 0, 0, 0, 0, 0, {}
    end

    -- ========================================================================
    -- 2. Уточнение истинного старта и пересчет конца первой волны
    -- ========================================================================
    local isUp = (trendDir == 1)
    local ext  = isUp and low or high
    local cmp  = isUp and function(a, b) return a < b end
                       or function(a, b) return a > b end

    -- А) Истинный экстремум на участке [1..endBar]
    local bestVal, bestIdx = ext[1], 1
    for k = 2, endBar do
        if cmp(ext[k], bestVal) then
            bestVal, bestIdx = ext[k], k
        end
    end
    lineStart, startBar = bestVal, bestIdx

    -- Б) Первый бар от startBar, дающий импульс >= deviation
    local target = isUp and high or low
    local target_dev = lineStart * dev_frac
    for k = startBar, #target do
        local diff = isUp and (target[k] - lineStart) or (lineStart - target[k])
        if diff >= target_dev then
            lineEnd, endBar = target[k], k
            break
        end
    end

    -- ========================================================================
    -- 3. Продолжение ЗигЗага по следующим свечам (от endBar + 1 до конца)
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