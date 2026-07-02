"""產生每日輿情摘要(選用)。

支援兩種 AI 後端(由 config.summary_provider 決定):
- "anthropic" — Claude API,需要 ANTHROPIC_API_KEY
- "ollama"    — 本機 Ollama(例如 kimi-k2),不需要雲端金鑰

任一後端失敗時回傳 None,主流程照常進行、不會中斷。
"""

from __future__ import annotations

import logging

import requests

from ..config import Config
from ..models import Post

log = logging.getLogger(__name__)


def generate_summary(posts: list[Post], config: Config) -> str | None:
    if not config.summary_enabled or not posts:
        return None

    provider = (config.summary_provider or "anthropic").strip().lower()
    prompt = _build_prompt(posts[: config.summary_max_posts], config)

    if provider == "ollama":
        return _ollama_summary(prompt, config)
    return _anthropic_summary(prompt, config)


# ---------------- Ollama(本機模型,例如 Kimi)----------------

def _ollama_summary(prompt: str, config: Config) -> str | None:
    base = (config.ollama_base_url or "http://localhost:11434").rstrip("/")
    model = config.ollama_model or "kimi-k2"
    headers = {}
    if config.ollama_api_key:
        # Ollama Cloud(https://ollama.com)用 Bearer key 驗證;本機 Ollama 會忽略此 header
        headers["Authorization"] = f"Bearer {config.ollama_api_key}"
    try:
        resp = requests.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            headers=headers,
            timeout=600,  # 大模型可能很慢,寬一點
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.ConnectionError:
        log.warning(
            "[summary] 連不到 Ollama(%s)。請確認 Ollama 有在執行(選單列圖示或 `ollama serve`)。",
            base,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning("[summary] Ollama 呼叫失敗(model=%s):%s", model, exc)
        return None

    text = ((data.get("message") or {}).get("content") or "").strip()
    if not text:
        log.warning("[summary] Ollama 回傳空內容(model=%s)。", model)
        return None
    return text


# ---------------- Anthropic(Claude API)----------------

def _anthropic_summary(prompt: str, config: Config) -> str | None:
    if not config.anthropic_api_key:
        log.info("[summary] 未設定 ANTHROPIC_API_KEY,略過 AI 摘要。")
        return None
    try:
        import anthropic
    except ImportError:
        log.warning("[summary] 未安裝 anthropic 套件(pip install anthropic),略過。")
        return None

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    try:
        resp = client.messages.create(
            model=config.summary_model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("[summary] 呼叫 Claude 失敗:%s", exc)
        return None

    if resp.stop_reason == "refusal":
        log.warning("[summary] 模型婉拒了此請求,略過摘要。")
        return None

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return text.strip() or None


# ---------------- 共用 prompt ----------------

def _build_prompt(posts: list[Post], config: Config) -> str:
    keywords = "、".join(config.keywords)
    lines: list[str] = []
    for i, p in enumerate(posts, 1):
        when = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "?"
        lines.append(
            f"{i}. [{p.platform}] ({when}, 讚 {p.score}/留言 {p.num_comments}) "
            f"{p.title or p.preview}\n   {p.preview}\n   {p.url}"
        )
    corpus = "\n".join(lines)

    return (
        f"你是一位輿情分析助理。以下是今天針對關鍵字「{keywords}」"
        f"從 Reddit / Dcard / Threads / Facebook 蒐集到的貼文清單。\n\n"
        f"請用「{config.summary_language}」產生一份精簡的每日輿情摘要,包含:\n"
        f"1. 整體重點(3~5 條,條列)\n"
        f"2. 整體情緒傾向(正面 / 中立 / 負面)與大致比例,並說明理由\n"
        f"3. 值得注意的貼文或趨勢(附上編號)\n"
        f"4. 若有負面或需要留意的訊號,特別點出\n\n"
        f"請務必只根據下列資料撰寫,不要杜撰。使用 Markdown 格式。\n\n"
        f"=== 貼文清單 ===\n{corpus}\n"
    )
