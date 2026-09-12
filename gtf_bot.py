//@version=5
indicator("GTF SOP v4.2 Multi-Timeframe Institutional Overlay", overlay=true, max_boxes_count=500, max_lines_count=500)

// -------------------------------------------------------------------------
// INPUTS & TIMEFRAME MAPPING
// -------------------------------------------------------------------------
i_htfTimeframe = input.timeframe("W", "HTF (Curve / Location Timeframe)", group="Multi-Timeframe Architecture")
i_itfTimeframe = input.timeframe("D", "ITF (Trending Timeframe)", group="Multi-Timeframe Architecture")
i_showHTFOnly  = input.bool(true, "Enforce Most Recent HTF Zone Only", group="Multi-Timeframe Architecture")

// Visual Settings
c_demand = input.color(color.new(color.green, 78), "Demand Zone Fill", group="Visual Styling")
c_supply = input.color(color.new(color.red, 78), "Supply Zone Fill", group="Visual Styling")

// -------------------------------------------------------------------------
// CANDLE METRIC CLASSIFIER
// -------------------------------------------------------------------------
f_isBase() =>
    float rng = high - low
    float bdy = math.abs(close - open)
    rng > 0 and (bdy / rng) <= 0.50

f_isExciting() =>
    float rng = high - low
    float bdy = math.abs(close - open)
    rng > 0 and (bdy / rng) > 0.50

isBase = f_isBase()
isExciting = f_isExciting()

// -------------------------------------------------------------------------
// EXECUTION TIMEFRAME FORMATIONS (B2W & EXCEPTIONAL MARKING)
// -------------------------------------------------------------------------
bool isDemandLegOut = isExciting and close > open and isBase[1]
float ltfDemandPL   = math.max(open[1], close[1])
float ltfDemandDL   = math.min(low[2], math.min(low[1], low[0]))

bool isSupplyLegOut = isExciting and close < open and isBase[1]
float ltfSupplyPL   = math.min(open[1], close[1])
float ltfSupplyDL   = math.max(high[2], math.max(high[1], high[0]))

var box[] ltfDemandBoxes = array.new<box>()
var box[] ltfSupplyBoxes = array.new<box>()

if isDemandLegOut
    box b = box.new(left=bar_index[1], top=ltfDemandPL, right=bar_index + 12, bottom=ltfDemandDL, 
      bgcolor=c_demand, border_color=color.green, border_style=line.style_solid)
    array.push(ltfDemandBoxes, b)
    if array.size(ltfDemandBoxes) > 5
        box.delete(array.shift(ltfDemandBoxes))

if isSupplyLegOut
    box b = box.new(left=bar_index[1], top=ltfSupplyDL, right=bar_index + 12, bottom=ltfSupplyPL, 
      bgcolor=c_supply, border_color=color.red, border_style=line.style_solid)
    array.push(ltfSupplyBoxes, b)
    if array.size(ltfSupplyBoxes) > 5
        box.delete(array.shift(ltfSupplyBoxes))

// -------------------------------------------------------------------------
// DYNAMIC MOVING AVERAGES & CROSSOVERS
// -------------------------------------------------------------------------
ema20 = ta.ema(close, 20)
ema50 = ta.ema(close, 50)
plot(ema20, "20 EMA", color=color.blue, linewidth=2)
plot(ema50, "50 EMA", color=color.orange, linewidth=2)

plotshape(ta.crossover(ema20, ema50), title="Golden Cross", style=shape.triangleup, location=location.belowbar, color=color.green, size=size.small)
plotshape(ta.crossunder(ema20, ema50), title="Death Cross", style=shape.triangledown, location=location.abovebar, color=color.red, size=size.small)
