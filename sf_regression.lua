-- sf_regression.lua
-- Расчет линейной регрессии (МНК), коэффициента Пирсона, границ канала
-- и продолжения линий тренда вперед, пока свечи пересекаются с коридором

function CalculateRegression(prices, startBar, endBar, k, highs, lows)
    startBar = startBar or 1
    endBar   = endBar or (prices and #prices or 1)
    k        = k or 2.0

    -- Единая таблица результата с безопасными дефолтными значениями
    local res = {}
    res.r          = 0
    res.slope      = 0
    res.intercept  = 0
    res.r2         = 0
    res.stdError   = 0
    res.currMid    = 0
    res.currUpper  = 0
    res.currLower  = 0
    res.startMid   = 0
    res.startUpper = 0
    res.startLower = 0
    res.startBar   = startBar
    res.endBar     = endBar
    res.extBar     = endBar
    res.extMid     = 0
    res.extUpper   = 0
    res.extLower   = 0

    -- Защитные проверки: если данных нет или мало — сразу возвращаем готовую структуру
    if not prices or #prices < 3 then
        return res
    end

    local n = endBar - startBar + 1
    if n < 3 then
        return res
    end

    -- ========================================================================
    -- 1. Вычисление базовых сумм МНК
    -- ========================================================================
    local sumX  = 0
    local sumY  = 0
    local sumX2 = 0
    local sumY2 = 0
    local sumXY = 0

    for i = 1, n do
        local x = i
        local y = prices[startBar + i - 1]
        sumX  = sumX + x
        sumY  = sumY + y
        sumX2 = sumX2 + x * x
        sumY2 = sumY2 + y * y
        sumXY = sumXY + x * y
    end

    local denomX = n * sumX2 - sumX * sumX
    local denomY = n * sumY2 - sumY * sumY

    if denomX == 0 then
        return res
    end

    -- ========================================================================
    -- 2. Наклон тренда a (slope) и смещение b (intercept)
    -- ========================================================================
    local a = (n * sumXY - sumX * sumY) / denomX
    local b = (sumY - a * sumX) / n

    -- ========================================================================
    -- 3. Коэффициент корреляции Пирсона r
    -- ========================================================================
    local r = 0
    local denomR = denomX * denomY
    if denomR > 0 then
        r = (n * sumXY - sumX * sumY) / math.sqrt(denomR)
    end

    -- ========================================================================
    -- 4. Стандартная ошибка регрессии Se (размах шума вокруг тренда)
    -- ========================================================================
    local sumE2 = 0
    for i = 1, n do
        local x = i
        local y = prices[startBar + i - 1]
        local yModel = a * x + b
        local e = y - yModel
        sumE2 = sumE2 + e * e
    end

    local se = math.sqrt(sumE2 / (n - 2))
    local bandOffset = k * se

    -- ========================================================================
    -- 5. Точки канала: на старте (x = 1) и на финише волны (x = n)
    -- ========================================================================
    local midStart   = a * 1 + b
    local upperStart = midStart + bandOffset
    local lowerStart = midStart - bandOffset

    local midEnd     = a * n + b
    local upperEnd   = midEnd + bandOffset
    local lowerEnd   = midEnd - bandOffset

    -- ========================================================================
    -- 6. Продолжение линий тренда вперед, пока свечи пересекаются с каналом
    -- ========================================================================
    local extBar = endBar
    if highs and lows and #highs >= endBar then
        for i = endBar + 1, #highs do
            local x = i - startBar + 1
            local mid = a * x + b
            local up  = mid + bandOffset
            local dn  = mid - bandOffset
            local h   = highs[i]
            local l   = lows[i]

            -- Свеча пересекается с каналом, если ее диапазон [l, h] перекрывает [dn, up]
            if h >= dn and l <= up then
                extBar = i
            else
                break
            end
        end
    end

    local extX = extBar - startBar + 1
    local extMid = a * extX + b
    local extUpper = extMid + bandOffset
    local extLower = extMid - bandOffset

    -- Заполняем вычисленные значения
    res.r          = r
    res.slope      = a
    res.intercept  = b
    res.r2         = r * r
    res.stdError   = se
    res.currMid    = midEnd
    res.currUpper  = upperEnd
    res.currLower  = lowerEnd
    res.startMid   = midStart
    res.startUpper = upperStart
    res.startLower = lowerStart
    res.extBar     = extBar
    res.extMid     = extMid
    res.extUpper   = extUpper
    res.extLower   = extLower

    return res
end