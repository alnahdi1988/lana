\# Trade Plan Contract



This document defines the exact output contract for the trade plan engine.



\## 1. Purpose



The trade plan engine receives a valid `LONG` signal and converts it into a practical plan.



It outputs:

\- entry zone

\- confirmation level

\- invalidation level

\- TP1

\- TP2

\- trail mode



This is separate from the signal engine.



---



\## 2. Input dependency



The trade plan engine should only run for:

\- signals where `signal == LONG`



It should not be asked to build a plan for `NONE`.



---



\## 3. Output schema



```json

{

&nbsp; "signal\_id": "sig\_12345",

&nbsp; "symbol": "UAMY",

&nbsp; "timestamp": "2026-03-08T15:45:00Z",

&nbsp; "entry\_type": "BASE",

&nbsp; "entry\_zone\_low": 9.18,

&nbsp; "entry\_zone\_high": 9.26,

&nbsp; "confirmation\_level": 9.31,

&nbsp; "invalidation\_level": 8.97,

&nbsp; "tp1": 9.58,

&nbsp; "tp2": 9.94,

&nbsp; "trail\_mode": "STRUCTURAL",

&nbsp; "plan\_reason\_codes": \[

&nbsp;   "ENTRY\_FROM\_RECONTAINMENT",

&nbsp;   "INVALIDATION\_BELOW\_BEHAVIORAL\_BLOCK",

&nbsp;   "TP1\_AT\_INTERNAL\_LIQUIDITY",

&nbsp;   "TP2\_AT\_HTF\_OBJECTIVE"

&nbsp; ]

}

4\. Required fields

signal\_id



Reference to the originating signal.



symbol



Ticker.



timestamp



Plan creation timestamp.



entry\_type



Must be one of:



AGGRESSIVE



BASE



CONFIRMATION



Default preferred type:



BASE



entry\_zone\_low / entry\_zone\_high



Numerical zone bounds.

Entry must be a zone, not a single exact price, unless explicitly unavoidable.



confirmation\_level



A price level above the base entry zone that confirms strength.



invalidation\_level



A structural invalidation level.

Must be structure-based, not arbitrary percentage-only logic.



tp1



Nearest realistic objective.



tp2



Higher timeframe objective.



trail\_mode



Must be one of:



STRUCTURAL



NONE



Default:



STRUCTURAL



plan\_reason\_codes



Machine-readable rationale.



5\. Entry philosophy



Entries must be structural and zone-based.



Preferred entry sources:



discount response area



equilibrium reclaim area



re-containment range



control candle body



micro imbalance / FVG zone



The system must not use:



random fixed-offset entries



breakout chase entries as the default



purely indicator-based entry prices



6\. Entry types

AGGRESSIVE



Use when:



doctrine signal is valid



reclaim or trigger has just appeared



entry is near first defended zone



This is earliest and least conservative.



BASE



Use as default.

Use when:



valid doctrine setup exists



price is in re-containment or ideal structural pullback zone



behavior is orderly



CONFIRMATION



Use when:



additional strength is required



bullish BOS or stronger LTF confirmation occurs after the initial trigger



This is safest but later.



7\. Invalidation philosophy



Invalidation must be based on structure, not arbitrary risk percentages.



Acceptable invalidation anchors:



below defended structural low



below behavioral block low



below reclaim failure point



below the structure whose break invalidates the long thesis



Invalidation must not be:



“2% below entry” without structural justification



just under a random candle wick



8\. Target philosophy

TP1



TP1 should be the nearest realistic objective, such as:



prior internal swing high



first liquidity pocket



equilibrium return if entry came from discount



immediate premium edge



TP2



TP2 should be a higher timeframe objective, such as:



external liquidity



prior major swing high



full premium expansion area



next major structural objective



Targets should be structure-driven.



9\. Trail mode

STRUCTURAL



Trail logic is conceptually based on:



newly formed defended lows



preserved higher-low sequence



structural integrity remaining intact



For v1, trail mode is descriptive output only, not auto-execution logic.



NONE



Used only if no trailing logic is intended.



10\. Plan reason codes



Allowed examples:



ENTRY\_FROM\_DISCOUNT



ENTRY\_FROM\_EQUILIBRIUM



ENTRY\_FROM\_RECONTAINMENT



ENTRY\_FROM\_RECLAIM



ENTRY\_FROM\_CONTROL\_CANDLE



ENTRY\_FROM\_MICRO\_IMBALANCE



INVALIDATION\_BELOW\_STRUCTURAL\_LOW



INVALIDATION\_BELOW\_BEHAVIORAL\_BLOCK



INVALIDATION\_BELOW\_RECLAIM\_FAILURE



TP1\_AT\_INTERNAL\_LIQUIDITY



TP1\_AT\_EQUILIBRIUM\_RETURN



TP2\_AT\_EXTERNAL\_LIQUIDITY



TP2\_AT\_HTF\_OBJECTIVE



11\. Delayed data rule



The trade plan must be realistic under delayed data.



This means:



the plan is built after the delayed signal becomes known



backtests must reflect that timing honestly



do not allow impossible fills based on unseen live data



12\. Non-goals



The trade plan contract does not include:



portfolio size



capital allocation



broker execution



partial fill simulation



slippage model in the contract itself



These belong elsewhere.

