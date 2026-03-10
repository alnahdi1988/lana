\# Doctrine Definitions



This document is the authoritative definition set for the structural doctrine engine.



\## 1. Scope



This doctrine is used to detect \*\*LONG-only structural setups\*\* in U.S. stocks priced between \*\*$5 and $50\*\*.



Timeframes used:

\- HTF = 4H

\- MTF = 1H

\- LTF = 15M

\- Optional micro confirmation = 5M



No signal is valid on one timeframe alone.



---



\## 2. Swing Structure



\### Swing High

A swing high is a pivot high where the high is greater than the highs of the previous `N` bars and the next `N` bars.



Default:

\- `N = 2`



\### Swing Low

A swing low is a pivot low where the low is lower than the lows of the previous `N` bars and the next `N` bars.



Default:

\- `N = 2`



These values must be configurable.



---



\## 3. BOS (Break of Structure)



\### Bullish BOS

A bullish BOS occurs when price \*\*closes above\*\* a prior meaningful swing high in the current structural context.



Requirements:

\- use close, not wick alone

\- breakout must occur through a previously recognized swing high

\- wick-only breaks are not enough



\### Bearish BOS

A bearish BOS occurs when price \*\*closes below\*\* a prior meaningful swing low.



For this system, bearish BOS is used only as context or invalidation, not for short signals.



---



\## 4. CHOCH (Change of Character)



\### Bullish CHOCH

A bullish CHOCH occurs when a prior short-term bearish sequence loses control and price closes above the last lower high or short-term structural cap.



\### Bearish CHOCH

A bearish CHOCH occurs when a prior short-term bullish sequence loses control and price closes below the last higher low or short-term structural floor.



For this system:

\- bullish CHOCH can be a trigger

\- bearish CHOCH can be an invalidation or caution event



---



\## 5. Compression



Compression is a structural tightening phase before a possible move.



Compression exists when all or most of these are true:

\- recent candle ranges are contracting

\- local swings are tightening

\- realized range is below rolling ATR baseline

\- price is coiling near a structural zone



Suggested baseline:

\- average range over last `N` bars < `0.75 × ATR(20)`



Compression is a state, not a trigger.



---



\## 6. Displacement



Displacement is an impulsive move through structure.



A bullish displacement exists when:

\- range expansion is clearly above recent norm

\- price closes through meaningful structure

\- the close is near the high of the bar or sequence



Suggested baseline:

\- bar or sequence range > `1.5 × ATR(20)`



Displacement can begin the trend leg but is not itself the preferred entry point.



---



\## 7. Reclaim



A reclaim occurs when price temporarily breaks a structural zone or liquidity pocket, then returns back inside and holds.



\### Bullish reclaim

Common bullish reclaim pattern:

\- price sweeps below a low or support reference

\- returns above it

\- holds it on subsequent bars



Bullish reclaim is a valid component for long setups.



---



\## 8. Fake Breakdown



A fake breakdown occurs when:

\- price breaks below a meaningful low or support

\- there is no sustained follow-through

\- price re-enters prior structure quickly



This often precedes a bullish reclaim.



---



\## 9. Trap-Reverse



Trap-reverse is a pattern where price appears to confirm downside continuation, attracts weak-handed exits, then reverses higher.



Valid trap-reverse components:

\- fake breakdown

\- reclaim

\- bullish CHOCH or BOS

\- location near discount or equilibrium



---



\## 10. Re-containment



Re-containment is one of the key setup states.



It occurs after displacement when:

\- continuation fails to extend immediately

\- price pulls back into the active range or structure

\- price stabilizes in equilibrium or discount

\- lower timeframe confirms renewed bullish intent



This is a preferred long setup area.



---



\## 11. Premium / Equilibrium / Discount



These zones are computed from the active swing range.



Given:

\- active swing high

\- active swing low



Then:

\- `equilibrium = (swing\_high + swing\_low) / 2`

\- price above equilibrium = premium

\- price below equilibrium = discount



\### Long preference

For long setups, preferred location is:

\- discount

\- equilibrium

\- reclaim from below equilibrium back toward equilibrium



Avoid chasing extended longs deep in premium unless higher-grade continuation logic explicitly supports it.



---



\## 12. Higher Timeframe Bias



HTF bullish bias exists when:

\- structure is bullish or constructive

\- bullish BOS is intact or prior bullish leg is not invalidated

\- meaningful higher lows are holding

\- price is not in confirmed breakdown

\- current pullback is still structurally healthy



Allowed outputs:

\- `BULLISH`

\- `NEUTRAL`

\- `BEARISH`



Only `BULLISH` may proceed to long evaluation.



---



\## 13. MTF Setup States



On the 1H timeframe, valid long setup states are:



\- `DISCOUNT\_RESPONSE`

\- `EQUILIBRIUM\_HOLD`

\- `RECONTAINMENT\_CONFIRMED`

\- `BULLISH\_RECLAIM`



Neutral / invalid states include:

\- `NO\_STRUCTURE`

\- `CHOP`

\- `INVALIDATED`

\- `EXTENDED\_PREMIUM`



---



\## 14. LTF Trigger States



On the 15M timeframe, valid bullish triggers include:



\- `BULLISH\_CHOCH`

\- `BULLISH\_BOS`

\- `BULLISH\_RECLAIM`

\- `FAKE\_BREAKDOWN\_REVERSAL`

\- `TRAP\_REVERSE\_BULLISH`



At least one valid bullish trigger must be present for a `LONG` signal.



---



\## 15. Cross-Frame Alignment



A valid long setup requires alignment.



Minimum:

\- HTF bullish

\- MTF valid bullish setup

\- LTF valid bullish trigger



If one of these is missing, no long signal is allowed.



Preferred:

\- all three frames clearly aligned



---



\## 16. Invalid Conditions



The doctrine must reject a long if any of these are true:

\- HTF is neutral or bearish

\- MTF setup is incomplete or invalidated

\- LTF trigger is absent

\- structure is choppy and unclear

\- price is too extended from equilibrium

\- event-risk suppression is active

\- market / sector regime disallows long continuation setups



---



\## 17. Structural Quality



A setup is higher quality if:

\- compression was clean

\- displacement was decisive

\- pullback is orderly

\- reclaim is clear

\- relative volume supports the move

\- stock is stronger than market and sector context

\- the setup appears in discount or equilibrium, not extended premium



Structural quality affects ranking, not the doctrine definition itself.

