# Architecture overview

The platform is designed around seven major layers:

1. Dataset management
2. Model provider adapters
3. Evaluation engine
4. Statistical analysis
5. Persistence
6. FastAPI backend
7. Streamlit dashboard

The code is intentionally separated so that evaluation logic can be exercised programmatically and also exposed through HTTP endpoints.