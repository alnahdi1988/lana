\# Architecture



\## 1. Overview



This system is a modular long-only structural signal platform for U.S. stocks.



It has five main layers:



1\. Data and universe

2\. Structural doctrine

3\. Trade planning

4\. Ranking and learning

5\. Delivery and monitoring



---



\## 2. Main services



\### universe\_service

Builds and refreshes the eligible stock universe.



\### polygon\_ingestor

Fetches delayed OHLCV data and stores it.



\### structure\_engine

Detects swing structure, BOS, CHOCH, and structural events.



\### zone\_engine

Computes premium / equilibrium / discount zones.



\### pattern\_engine

Detects compression, displacement, reclaim, fake breakdown, trap-reverse, and re-containment.



\### regime\_engine

Determines market and sector regime.



\### event\_risk\_engine

Suppresses setups around earnings and major event risk.



\### signal\_engine

Produces only:

\- `LONG`

\- `NONE`



\### trade\_plan\_engine

Builds:

\- entry zone

\- confirmation level

\- invalidation

\- TP1

\- TP2

\- trail mode



\### ranking\_engine

Ranks valid signals and assigns confidence / grade.



\### telegram\_notifier

Sends only top-quality alerts.



\### outcome\_tracker

Tracks signal outcomes and creates labels.



\### trainer\_service

Retrains ranking models from signal history.



---



\## 3. Data flow



1\. Polygon ingests bars

2\. Universe filter keeps valid stocks

3\. Feature and structural events are built

4\. Regime and event risk are applied

5\. Signal engine decides `LONG` or `NONE`

6\. Trade plan engine creates a plan for `LONG`

7\. Ranking engine assigns confidence and grade

8\. Telegram sends only A+/A alerts

9\. Outcome tracker labels results

10\. Trainer updates ranking model



---



\## 4. Storage



Use:

\- PostgreSQL

\- TimescaleDB

\- Redis



Primary persisted objects:

\- symbols

\- universe snapshots

\- bars

\- features

\- signals

\- trade plans

\- outcomes

\- model runs



---



\## 5. APIs



Minimum APIs:

\- `/health`

\- `/universe`

\- `/signals/latest`

\- `/signals/{ticker}`

\- `/research/performance`

\- admin endpoints for rebuild/retrain



---



\## 6. Deployment



Preferred stack:

\- Python 3.11+

\- FastAPI

\- PostgreSQL + TimescaleDB

\- Redis

\- Celery

\- Docker Compose



v1 deployment goal:

\- local or single-host deployment

\- stable scheduled scans every 15 minutes

\- nightly retraining / reporting



---



\## 7. Design rules



\- doctrine logic is deterministic

\- ML ranks doctrine-valid setups only

\- signal engine and trade plan engine must remain separate

\- delayed-data assumptions must remain honest

\- prefer `NONE` over forced signals

