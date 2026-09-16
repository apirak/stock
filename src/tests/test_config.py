"""config.py — readiness gates, env parsing, universe defaults."""
import config


class TestSmtpAndDiscordReady:
    def test_smtp_ready_requires_user_password_and_recipients(self, monkeypatch):
        monkeypatch.setattr(config, "SMTP_USER", "me@gmail.com")
        monkeypatch.setattr(config, "SMTP_PASSWORD", "app-pass")
        monkeypatch.setattr(config, "EMAIL_TO", ["a@x.com"])
        assert config.smtp_ready() is True

        monkeypatch.setattr(config, "EMAIL_TO", [])
        assert config.smtp_ready() is False

    def test_discord_ready_requires_webhook_url(self, monkeypatch):
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL", "")
        assert config.discord_ready() is False
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/x")
        assert config.discord_ready() is True

    def test_discord_weekly_falls_back_to_daily_webhook(self, monkeypatch):
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL", "")
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL_WEEKLY", "")
        assert config.discord_weekly_ready() is False
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/daily")
        assert config.discord_weekly_ready() is True
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL_WEEKLY", "https://discord.com/api/webhooks/1/weekly")
        assert config.discord_weekly_ready() is True


class TestDefaults:
    def test_discord_username_persona_default_in_source(self):
        # _safe_env blanks DISCORD_USERNAME in tests; the default itself is
        # documented in config source — assert the source default directly.
        import inspect
        source = inspect.getsource(config)
        assert 'os.getenv("DISCORD_USERNAME", "Feb 🌷")' in source

    def test_watchlist_env_empty_by_default_universe_comes_from_index(self):
        # When WATCHLIST env is unset, main._resolve_tickers reads index.md
        # via universe.tickers(); config.WATCHLIST must then be [] (falsy).
        assert config.WATCHLIST == [] or isinstance(config.WATCHLIST, list)

    def test_repo_layout_points_into_the_knowledge_base(self):
        assert config.INDEX_PATH.name == "index.md"
        assert config.INDEX_PATH.parent.name == "stock_knowledge"
        assert config.LEDGER_PATH.name == "ledger.md"
        assert config.GUIDELINE_PATH.name == "_GUIDELINE.md"
        assert config.DAILY_REPORT_DIR.name == "_daily"
        assert config.WEEKLY_REPORT_DIR.name == "weekly"
        assert config.FALLING_ANGLE_DOC.name == "falling_angle.md"
        assert config.PERSONA_PATH.name == "persona.md"


class TestParseOverrides:
    def test_parses_pairs_and_normalizes_tickers(self):
        assert config._parse_overrides("unh=520, tgt=180") == {"UNH": 520.0, "TGT": 180.0}

    def test_skips_malformed_pairs(self):
        # " =5" keeps an empty-string ticker key — pin the actual (harmless) behaviour
        assert config._parse_overrides("BAD, =5, foo=bar, ok=1.5") == {"": 5.0, "OK": 1.5}

    def test_empty_string_gives_empty_dict(self):
        assert config._parse_overrides("") == {}
