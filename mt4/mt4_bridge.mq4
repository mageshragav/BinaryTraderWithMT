//+------------------------------------------------------------------+
//|                                               mt4_bridge.mq4     |
//|                                 Multi-Agent Trading System Bridge|
//|                                   ZeroMQ Publisher for MT4       |
//+------------------------------------------------------------------+
#property copyright "Trading Multi-Agent System"
#property version   "1.00"
#property strict

// Include ZeroMQ library for MT4
#include <ZeroMQ.mqh>

//+------------------------------------------------------------------+
//| Configuration                                                    |
//+------------------------------------------------------------------+
input string   ZMQ_HOST          = "tcp://127.0.0.1";  // ZeroMQ host
input int      ZMQ_PORT          = 5555;               // ZeroMQ port
input string   SYMBOL            = "EURUSD";           // Trading symbol
input ENUM_TIMEFRAMES TIMEFRAME = PERIOD_M15;         // Chart timeframe
input int      SEND_INTERVAL_MS  = 5000;               // Send interval in ms

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
zmq_context    Context;
zmq_socket     Publisher;
ulong          LastSendTime = 0;
bool           IsInitialized = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    // Initialize ZeroMQ context
    Context = zmq_context_create();
    if(Context == NULL)
    {
        Print("ERROR: Failed to create ZeroMQ context");
        return(INIT_FAILED);
    }
    
    // Create PUB socket
    Publisher = zmq_socket_create(Context, ZMQ_PUB);
    if(Publisher == NULL)
    {
        Print("ERROR: Failed to create ZeroMQ socket");
        return(INIT_FAILED);
    }
    
    // Connect to backend
    string endpoint = StringFormat("%s:%d", ZMQ_HOST, ZMQ_PORT);
    int result = zmq_connect(Publisher, endpoint);
    if(result != 0)
    {
        Print("ERROR: Failed to connect to ZeroMQ endpoint: ", endpoint);
        return(INIT_FAILED);
    }
    
    Print("INFO: ZeroMQ bridge initialized successfully");
    Print("INFO: Publishing to ", endpoint);
    
    IsInitialized = true;
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    if(Publisher != NULL)
    {
        zmq_close(Publisher);
    }
    if(Context != NULL)
    {
        zmq_ctx_destroy(Context);
    }
    Print("INFO: ZeroMQ bridge shutdown");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    if(!IsInitialized) return;
    
    // Check if it's time to send data
    ulong currentTime = GetTickCount();
    if(currentTime - LastSendTime < SEND_INTERVAL_MS) return;
    
    LastSendTime = currentTime;
    
    // Collect and send indicator data
    SendIndicatorData();
}

//+------------------------------------------------------------------+
//| Collect and send indicator data                                  |
//+------------------------------------------------------------------+
void SendIndicatorData()
{
    // Build JSON payload with indicator data
    string jsonPayload = BuildIndicatorJSON();
    
    if(jsonPayload == "")
    {
        Print("ERROR: Failed to build indicator JSON");
        return;
    }
    
    // Send via ZeroMQ
    string topic = "mt4_signal";
    zmq_msg_t msg;
    zmq_msg_init_data(msg, StringToCharArray(jsonPayload));
    
    int result = zmq_send(Publisher, topic, msg, 0);
    if(result < 0)
    {
        Print("ERROR: Failed to send ZeroMQ message");
    }
    else
    {
        Print("INFO: Sent indicator data for ", SYMBOL, " ", EnumToString(TIMEFRAME));
    }
}

//+------------------------------------------------------------------+
//| Indicator Signal Prediction Functions                            |
//+------------------------------------------------------------------+

// Get CALL/PUT/WAIT signal for SMA crossover
string GetSMA_Signal(double sma_short, double sma_long, double current_price)
{
    if(sma_short > sma_long && current_price > sma_short) return "CALL";
    if(sma_short < sma_long && current_price < sma_short) return "PUT";
    return "WAIT";
}

// Get EMA crossover signal
string GetEMA_Signal(double ema_fast, double ema_slow, double current_price)
{
    if(ema_fast > ema_slow && current_price > ema_fast) return "CALL";
    if(ema_fast < ema_slow && current_price < ema_fast) return "PUT";
    return "WAIT";
}

// Get ADX signal (trend strength)
string GetADX_Signal(double adx, double plus_di, double minus_di)
{
    if(adx < 20) return "WAIT"; // Weak trend
    if(plus_di > minus_di && plus_di - minus_di > 5) return "CALL";
    if(minus_di > plus_di && minus_di - plus_di > 5) return "PUT";
    return "WAIT";
}

// Get RSI signal
string GetRSI_Signal(double rsi)
{
    if(rsi < 30) return "CALL"; // Oversold
    if(rsi > 70) return "PUT";  // Overbought
    return "WAIT";
}

// Get Stochastic signal
string GetStoch_Signal(double stoch_k, double stoch_d)
{
    if(stoch_k < 20 && stoch_k > stoch_d) return "CALL";
    if(stoch_k > 80 && stoch_k < stoch_d) return "PUT";
    return "WAIT";
}

// Get MACD signal
string GetMACD_Signal(double macd_main, double macd_signal, double macd_hist)
{
    if(macd_main > macd_signal && macd_hist > 0) return "CALL";
    if(macd_main < macd_signal && macd_hist < 0) return "PUT";
    return "WAIT";
}

// Get CCI signal
string GetCCI_Signal(double cci)
{
    if(cci < -100) return "CALL";
    if(cci > 100) return "PUT";
    return "WAIT";
}

// Get Williams %R signal
string GetWPR_Signal(double wpr)
{
    if(wpr < -80) return "CALL";
    if(wpr > -20) return "PUT";
    return "WAIT";
}

// Get Bollinger Bands signal
string GetBB_Signal(double price, double bb_upper, double bb_middle, double bb_lower)
{
    if(price <= bb_lower) return "CALL"; // Price at lower band
    if(price >= bb_upper) return "PUT";  // Price at upper band
    if(price > bb_middle) return "CALL";
    if(price < bb_middle) return "PUT";
    return "WAIT";
}

// Get MFI signal
string GetMFI_Signal(double mfi)
{
    if(mfi < 20) return "CALL";
    if(mfi > 80) return "PUT";
    return "WAIT";
}

//+------------------------------------------------------------------+
//| Build JSON payload with all indicators and their predictions     |
//+------------------------------------------------------------------+
string BuildIndicatorJSON()
{
    string json = "{";
    double current_price = (MarketInfo(SYMBOL, MODE_BID) + MarketInfo(SYMBOL, MODE_ASK)) / 2.0;
    
    // Basic info
    json += "\"symbol\":\"" + SYMBOL + "\",";
    json += "\"timeframe\":\"" + TimeframeToString(TIMEFRAME) + "\",";
    json += "\"timestamp\":" + IntegerToString(TimeCurrent()) + ",";
    json += "\"bid\":" + DoubleToString(MarketInfo(SYMBOL, MODE_BID), Digits()) + ",";
    json += "\"ask\":" + DoubleToString(MarketInfo(SYMBOL, MODE_ASK), Digits()) + ",";
    
    // Trend indicators with predictions
    double sma_20 = iMA(SYMBOL, TIMEFRAME, 20, 0, MODE_SMA, PRICE_CLOSE, 0);
    double sma_50 = iMA(SYMBOL, TIMEFRAME, 50, 0, MODE_SMA, PRICE_CLOSE, 0);
    double sma_200 = iMA(SYMBOL, TIMEFRAME, 200, 0, MODE_SMA, PRICE_CLOSE, 0);
    double ema_12 = iMA(SYMBOL, TIMEFRAME, 12, 0, MODE_EMA, PRICE_CLOSE, 0);
    double ema_26 = iMA(SYMBOL, TIMEFRAME, 26, 0, MODE_EMA, PRICE_CLOSE, 0);
    double adx_14 = iADX(SYMBOL, TIMEFRAME, 14, PRICE_CLOSE, 0);
    double plus_di = iADX(SYMBOL, TIMEFRAME, 14, PRICE_CLOSE, 1);
    double minus_di = iADX(SYMBOL, TIMEFRAME, 14, PRICE_CLOSE, 2);
    
    json += "\"trend\":{";
    json += "\"sma_20\":{\"value\":" + DoubleToString(sma_20, Digits()) + ",\"prediction\":\"" + GetSMA_Signal(sma_20, sma_50, current_price) + "\"},";
    json += "\"sma_50\":{\"value\":" + DoubleToString(sma_50, Digits()) + ",\"prediction\":\"" + GetSMA_Signal(sma_50, sma_200, current_price) + "\"},";
    json += "\"sma_200\":{\"value\":" + DoubleToString(sma_200, Digits()) + ",\"prediction\":\"NEUTRAL\"},";
    json += "\"ema_12\":{\"value\":" + DoubleToString(ema_12, Digits()) + ",\"prediction\":\"" + GetEMA_Signal(ema_12, ema_26, current_price) + "\"},";
    json += "\"ema_26\":{\"value\":" + DoubleToString(ema_26, Digits()) + ",\"prediction\":\"NEUTRAL\"},";
    json += "\"adx_14\":{\"value\":" + DoubleToString(adx_14, Digits()) + ",\"prediction\":\"" + GetADX_Signal(adx_14, plus_di, minus_di) + "\"},";
    json += "\"plus_di\":{\"value\":" + DoubleToString(plus_di, Digits()) + "},";
    json += "\"minus_di\":{\"value\":" + DoubleToString(minus_di, Digits()) + "}";
    json += "},";
    
    // Momentum indicators with predictions
    double rsi_14 = iRSI(SYMBOL, TIMEFRAME, 14, PRICE_CLOSE, 0);
    double stoch_k = iStochastic(SYMBOL, TIMEFRAME, 5, 3, 3, MODE_SMA, STO_LOWHIGH, 0);
    double stoch_d = iStochastic(SYMBOL, TIMEFRAME, 5, 3, 3, MODE_SMA, STO_LOWHIGH, 1);
    double macd_main = iMACD(SYMBOL, TIMEFRAME, 12, 26, 9, PRICE_CLOSE, 0);
    double macd_signal = iMACD(SYMBOL, TIMEFRAME, 12, 26, 9, PRICE_CLOSE, 1);
    double macd_hist = macd_main - macd_signal;
    double cci_20 = iCCI(SYMBOL, TIMEFRAME, 20, PRICE_TYPICAL, 0);
    double williams_r = iWPR(SYMBOL, TIMEFRAME, 14, 0);
    
    json += "\"momentum\":{";
    json += "\"rsi_14\":{\"value\":" + DoubleToString(rsi_14, Digits()) + ",\"prediction\":\"" + GetRSI_Signal(rsi_14) + "\"},";
    json += "\"stoch_k\":{\"value\":" + DoubleToString(stoch_k, Digits()) + ",\"prediction\":\"" + GetStoch_Signal(stoch_k, stoch_d) + "\"},";
    json += "\"stoch_d\":{\"value\":" + DoubleToString(stoch_d, Digits()) + "},";
    json += "\"macd_main\":{\"value\":" + DoubleToString(macd_main, Digits()) + ",\"prediction\":\"" + GetMACD_Signal(macd_main, macd_signal, macd_hist) + "\"},";
    json += "\"macd_signal\":{\"value\":" + DoubleToString(macd_signal, Digits()) + "},";
    json += "\"macd_hist\":{\"value\":" + DoubleToString(macd_hist, Digits()) + "},";
    json += "\"cci_20\":{\"value\":" + DoubleToString(cci_20, Digits()) + ",\"prediction\":\"" + GetCCI_Signal(cci_20) + "\"},";
    json += "\"williams_r\":{\"value\":" + DoubleToString(williams_r, Digits()) + ",\"prediction\":\"" + GetWPR_Signal(williams_r) + "\"}";
    json += "},";
    
    // Volatility indicators with predictions
    double bb_upper = iBands(SYMBOL, TIMEFRAME, 20, 0, 2.0, PRICE_CLOSE, 0, MODE_MAIN, 0);
    double bb_middle = iBands(SYMBOL, TIMEFRAME, 20, 0, 2.0, PRICE_CLOSE, 0, MODE_MAIN, 1);
    double bb_lower = iBands(SYMBOL, TIMEFRAME, 20, 0, 2.0, PRICE_CLOSE, 0, MODE_MAIN, 2);
    double atr_14 = iATR(SYMBOL, TIMEFRAME, 14, 0);
    double std_dev = iStdDev(SYMBOL, TIMEFRAME, 20, 0, MODE_SMA, PRICE_CLOSE, 0);
    
    json += "\"volatility\":{";
    json += "\"bb_upper\":{\"value\":" + DoubleToString(bb_upper, Digits()) + "},";
    json += "\"bb_middle\":{\"value\":" + DoubleToString(bb_middle, Digits()) + "},";
    json += "\"bb_lower\":{\"value\":" + DoubleToString(bb_lower, Digits()) + "},";
    json += "\"bb_signal\":{\"prediction\":\"" + GetBB_Signal(current_price, bb_upper, bb_middle, bb_lower) + "\"},";
    json += "\"atr_14\":{\"value\":" + DoubleToString(atr_14, Digits()) + "},";
    json += "\"std_dev\":{\"value\":" + DoubleToString(std_dev, Digits()) + "}";
    json += "},";
    
    // Volume indicators with predictions
    long volume = iVolume(SYMBOL, TIMEFRAME, 0);
    double obv = iOBV(SYMBOL, TIMEFRAME, PRICE_CLOSE, 0);
    double mfi_14 = iMFI(SYMBOL, TIMEFRAME, 14, 0);
    double force_index = iForce(SYMBOL, TIMEFRAME, 13, MODE_EMA, PRICE_CLOSE, 0);
    
    json += "\"volume\":{";
    json += "\"volume\":{\"value\":" + IntegerToString(volume) + "},";
    json += "\"obv\":{\"value\":" + DoubleToString(obv, 0) + "},";
    json += "\"mfi_14\":{\"value\":" + DoubleToString(mfi_14, Digits()) + ",\"prediction\":\"" + GetMFI_Signal(mfi_14) + "\"},";
    json += "\"force_index\":{\"value\":" + DoubleToString(force_index, Digits()) + "}";
    json += "},";
    
    // Price action
    json += "\"price_action\":{";
    json += "\"high\":{\"value\":" + DoubleToString(iHigh(SYMBOL, TIMEFRAME, 0), Digits()) + "},";
    json += "\"low\":{\"value\":" + DoubleToString(iLow(SYMBOL, TIMEFRAME, 0), Digits()) + "},";
    json += "\"open\":{\"value\":" + DoubleToString(iOpen(SYMBOL, TIMEFRAME, 0), Digits()) + "},";
    json += "\"close\":{\"value\":" + DoubleToString(iClose(SYMBOL, TIMEFRAME, 0), Digits()) + "}";
    json += "}";
    
    json += "}";
    
    return json;
}

//+------------------------------------------------------------------+
//| Convert timeframe to string                                      |
//+------------------------------------------------------------------+
string TimeframeToString(ENUM_TIMEFRAMES tf)
{
    switch(tf)
    {
        case PERIOD_M1:  return "M1";
        case PERIOD_M5:  return "M5";
        case PERIOD_M15: return "M15";
        case PERIOD_M30: return "M30";
        case PERIOD_H1:  return "H1";
        case PERIOD_H4:  return "H4";
        case PERIOD_D1:  return "D1";
        case PERIOD_W1:  return "W1";
        case PERIOD_MN1: return "MN1";
        default:         return "UNKNOWN";
    }
}

//+------------------------------------------------------------------+
//| Convert double to JSON-safe string                               |
//+------------------------------------------------------------------+
string DoubleToString(double value, int digits)
{
    if(value == EMPTY_VALUE || value != value) // Check for NaN
        return "null";
    return DoubleToString(value, digits);
}
//+------------------------------------------------------------------+
