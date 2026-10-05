# Streamlit replacement parity

The Next.js client is the primary end-user interface. Streamlit remains available as a temporary admin/debug client while the replacement is observed in normal use.

| Capability | Next.js route | Verification |
| --- | --- | --- |
| Seven-day dashboard, completion status, wealth/health/learning metrics | `/` | Unit helpers, production build, Playwright dashboard workflow |
| Conversation history, text, audio, image, streaming, editable confirmation | `/chat` | Component/unit tests and Playwright reachability workflow |
| Wealth filters, summaries, charts, CSV, edit, confirmed delete | `/wealth` | Record-editor unit test and Playwright edit workflow |
| Health filters, summaries, chart, CSV, edit, confirmed delete | `/health` | Shared typed record workspace and production build |
| Learning history, metrics, semantic/keyword search, safe source links, edit/delete | `/learning` | Playwright search/evidence workflow |
| Saved weekly reviews and supporting evidence | `/weekly-review` | Playwright review workflow |
| Preferences, provider readiness, public ZIP export, local snapshot | `/settings` | Export privacy unit test and Playwright settings workflow |

The replacement uses the same public FastAPI contracts as Streamlit. Raw chat inputs and original private record inputs are intentionally excluded from portable exports. Weekly-review generation remains a P6 backend capability; this client displays saved reviews and the backend's current availability message.

Before removing Streamlit entirely, observe the Next.js client with normal local data, confirm backup/restore operations through the planned production-readiness work, and retain a rollback path for at least one release.
