//+------------------------------------------------------------------+
//|                                                    Sample EA.mq5 |
//+------------------------------------------------------------------+
#property copyright "Test"
#property version   "1.00"
#property description "Sample grid + moving average expert for unit tests"

#include <Trade/Trade.mqh>
#include <Trade/SymbolInfo.mqh>

CTrade trade;

input double Lots        = 0.10;   // Khoi luong
input int    MaPeriod    = 20;
input int    RsiPeriod   = 14;
input double GridStep    = 15.0;
input bool   UseTrailing = true;

int ma_handle = INVALID_HANDLE;
int rsi_handle = INVALID_HANDLE;

/* Khoi tao cac indicator handle */
int OnInit()
{
   ma_handle = iMA(_Symbol, PERIOD_M15, MaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   rsi_handle = iRSI(_Symbol, PERIOD_M15, RsiPeriod, PRICE_CLOSE);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   IndicatorRelease(ma_handle);
}

double MaValue()
{
   double buffer[];
   CopyBuffer(ma_handle, 0, 0, 1, buffer);
   return(buffer[0]);
}

void OnTick()
{
   // Trend following entry
   double ma = MaValue();
   double price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(price > ma)
      trade.Buy(Lots, _Symbol);
   else
      trade.Sell(Lots, _Symbol);
}
