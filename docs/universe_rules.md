\# Universe Rules



\## 1. Scope



This system scans only U.S. stocks.



Allowed exchanges:

\- NYSE

\- NASDAQ

\- NYSE Arca

\- AMEX



---



\## 2. Hard eligibility filters



A stock is eligible only if all of these are true:



\- listed on an allowed U.S. exchange

\- last price between \*\*$5 and $50\*\*

\- average daily volume over 20 days is at least \*\*500,000 shares\*\*

\- average daily dollar volume over 20 days is at least \*\*$5,000,000\*\*

\- sufficient historical bar history is available

\- symbol is active

\- data quality is acceptable



These thresholds must be configurable.



---



\## 3. Recommended exclusions



Unless explicitly allowed, exclude:

\- ETFs

\- rights

\- warrants

\- preferred shares

\- OTC symbols

\- extremely illiquid names

\- symbols with repeated bad or missing data

\- symbols in active halt state



---



\## 4. Optional quality filters



These do not necessarily exclude a stock, but they affect ranking:



\- relative volume

\- spread quality

\- ATR percentile

\- sector strength

\- market cap floor

\- recent gap behavior

\- price efficiency / trend cleanliness



---



\## 5. Tiering



Eligible stocks should be divided into tiers.



\### Tier 1

Best-quality candidates.

Use for highest priority scans and alerts.



\### Tier 2

Tradable but lower-quality candidates.



\### Tier 3

Technically eligible but too noisy or weak for practical alerting.



---



\## 6. Daily universe refresh



The universe should refresh:

\- premarket

\- after market close

\- optional intraday refresh every 30–60 minutes



Universe snapshots must be stored historically.



---



\## 7. Final rule



The doctrine engine must not evaluate symbols that fail hard universe eligibility.

