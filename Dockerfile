# 輿情搜尋器 — Cloud Run / 任何容器平台通用
FROM python:3.11-slim

WORKDIR /app

# 先裝依賴(利用 Docker layer cache,改程式碼不用重裝套件)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run 會用環境變數 PORT 指定埠(預設 8080)
EXPOSE 8080
CMD streamlit run streamlit_app.py \
    --server.port=${PORT:-8080} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
