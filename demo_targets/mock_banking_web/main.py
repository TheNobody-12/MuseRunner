"""MockBank Enterprise Portal — deterministic demo target for MuseRunner.

A FastAPI application that serves a wire-transfer form with an optional
``?chaos_mode=true`` query parameter that dynamically renames the submit
button's ID to simulate a broken frontend deployment.

Usage::

    uvicorn demo_targets.mock_banking_web.main:app --port 8080

Then visit:
    Normal mode  →  http://localhost:8080/
    Chaos mode   →  http://localhost:8080/?chaos_mode=true
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(
    title="MockBank Enterprise Portal",
    description="Deterministic demo target for MuseRunner self-healing tests",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

def _render_transfer_page(chaos_mode: bool = False) -> str:
    """Render the wire transfer form HTML.

    When *chaos_mode* is True the submit button ID changes from
    ``confirm-transfer-btn`` to ``btn-legacy-v2-obfuscated-99``,
    simulating a real-world frontend deployment that breaks selectors.
    """
    btn_id = "btn-legacy-v2-obfuscated-99" if chaos_mode else "confirm-transfer-btn"
    chaos_badge = (
        '<span class="badge badge-danger">⚡ CHAOS MODE ON</span>'
        if chaos_mode
        else '<span class="badge badge-ok">✅ Normal Mode</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MockBank — Wire Transfer</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1923;
            color: #e8eaed;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .card {{
            background: #1a2733;
            border: 1px solid #2d3d4f;
            border-radius: 12px;
            padding: 2.5rem;
            width: 100%;
            max-width: 460px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }}
        h1 {{
            font-size: 1.5rem;
            margin-bottom: 0.25rem;
            color: #4fc3f7;
        }}
        .subtitle {{
            font-size: 0.85rem;
            color: #78909c;
            margin-bottom: 1.5rem;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
        }}
        .badge-danger {{
            background: rgba(244, 67, 54, 0.15);
            color: #ef5350;
            border: 1px solid rgba(244, 67, 54, 0.3);
        }}
        .badge-ok {{
            background: rgba(76, 175, 80, 0.15);
            color: #66bb6a;
            border: 1px solid rgba(76, 175, 80, 0.3);
        }}
        label {{
            display: block;
            font-size: 0.8rem;
            font-weight: 600;
            color: #90a4ae;
            margin-bottom: 0.3rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        input[type="text"],
        input[type="number"] {{
            width: 100%;
            padding: 0.7rem 1rem;
            margin-bottom: 1rem;
            border: 1px solid #2d3d4f;
            border-radius: 8px;
            background: #0f1923;
            color: #e8eaed;
            font-size: 0.95rem;
            transition: border-color 0.2s;
        }}
        input:focus {{
            outline: none;
            border-color: #4fc3f7;
        }}
        button {{
            width: 100%;
            padding: 0.8rem;
            border: none;
            border-radius: 8px;
            background: linear-gradient(135deg, #4fc3f7, #0288d1);
            color: #fff;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
            margin-top: 0.5rem;
        }}
        button:hover {{ opacity: 0.9; }}
        .footer {{
            text-align: center;
            margin-top: 1.5rem;
            font-size: 0.75rem;
            color: #546e7a;
        }}
        .footer a {{ color: #4fc3f7; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>🏦 MockBank Wire Transfer</h1>
        <p class="subtitle">MuseRunner Demo Target Application</p>
        {chaos_badge}

        <form action="/api/transfer" method="post" id="transfer-form">
            <label for="account-number">Account Number</label>
            <input type="text" id="account-number" name="account_number"
                   placeholder="e.g. 1234567890" required />

            <label for="ssn">SSN / SIN</label>
            <input type="text" id="ssn" name="ssn"
                   placeholder="e.g. 123-45-6789" required />

            <label for="amount">Amount ($)</label>
            <input type="number" id="amount" name="amount"
                   placeholder="e.g. 5000" min="1" required />

            <button type="submit" id="{btn_id}">Confirm Transfer</button>
        </form>

        <div class="footer">
            Submit button ID: <code>#{btn_id}</code><br/>
            <a href="/?chaos_mode={'false' if chaos_mode else 'true'}">
                Toggle {'Normal' if chaos_mode else 'Chaos'} Mode
            </a>
        </div>
    </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def transfer_form(chaos_mode: bool = False) -> HTMLResponse:
    """Serve the wire transfer form.

    Pass ``?chaos_mode=true`` to rename the submit button ID and trigger
    MuseRunner's self-healing agent.
    """
    return HTMLResponse(content=_render_transfer_page(chaos_mode))


@app.post("/api/transfer")
async def submit_transfer(request: Request) -> JSONResponse:
    """Accept a wire transfer form submission and return a mock confirmation."""
    form = await request.form()
    return JSONResponse(content={
        "status": "submitted",
        "reference": "TXN-MOCK-001",
        "account": form.get("account_number", ""),
        "amount": form.get("amount", ""),
        "message": "Wire transfer queued for processing.",
    })


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health endpoint for automated checks."""
    return {"status": "healthy", "service": "mockbank"}
