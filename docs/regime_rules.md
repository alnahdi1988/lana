\# Regime Rules



\## 1. Purpose



Regime controls when long setups are allowed and how strict the signal engine should be.



The same doctrine setup behaves differently across market conditions.



---



\## 2. Regime layers



The system must evaluate:



1\. Broad market regime

2\. Sector regime

3\. Stock-relative regime



---



\## 3. Broad market regime classes



Allowed regime labels:



\- `BULLISH\_TREND`

\- `CHOP`

\- `RISK\_OFF`

\- `HIGH\_VOL\_EXPANSION`

\- `WEAK\_DRIFT`



Inputs may include:

\- SPY structure

\- QQQ structure

\- IWM structure

\- realized volatility

\- breadth proxies

\- relative strength dispersion



---



\## 4. Sector regime classes



Each stock’s sector should also receive a regime label.



Examples:

\- `SECTOR\_STRONG`

\- `SECTOR\_NEUTRAL`

\- `SECTOR\_WEAK`



Inputs may include:

\- sector ETF structure

\- sector relative strength vs SPY

\- sector momentum persistence



---



\## 5. Regime effects



\### BULLISH\_TREND

Best environment for:

\- discount response

\- equilibrium hold

\- re-containment continuation

\- bullish reclaim



\### CHOP

Reduce confidence.

Require stronger structural quality.

Prefer fewer alerts.



\### RISK\_OFF

Suppress most long alerts.

Only allow strongest exceptional relative-strength setups if explicitly configured.



\### HIGH\_VOL\_EXPANSION

Allow continuation setups but increase caution around invalidations.



\### WEAK\_DRIFT

Allow selective setups only.

Prefer cleaner structures and stronger sector support.



---



\## 6. Final regime policy



A signal may only be emitted if:

\- market regime allows long setups

\- sector regime is not clearly hostile

\- stock-specific structure is aligned



Recommended concept:

\- Market Permission

\- Sector Permission

\- Stock Structure Quality



If market permission is weak, the engine should become more conservative.



---



\## 7. Regime output fields



Regime engine should expose:

\- market\_regime

\- sector\_regime

\- market\_permission\_score

\- sector\_permission\_score

\- regime\_reason\_codes

