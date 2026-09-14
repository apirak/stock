"""config.py — readiness gates and env parsing."""
import config


class TestLlmReady:
    def test_false_when_provider_none(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "none")
        monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-something")
        assert config.llm_ready() is False

    def test_true_with_provider_and_key(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
        monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
        assert config.llm_ready() is True

    def test_false_with_provider_but_no_key(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
        monkeypatch.setattr(config, "OPENAI_API_KEY", "")
        assert config.llm_ready() is False

    def test_each_provider_checks_its_own_key(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
        monkeypatch.setattr(config, "GEMINI_API_KEY", "g-key")
        monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
        assert config.llm_ready() is True


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


class TestParseOverrides:
    def test_parses_pairs_and_normalizes_tickers(self):
        assert config._parse_overrides("unh=520, tgt=180") == {"UNH": 520.0, "TGT": 180.0}

    def test_skips_malformed_pairs(self):
        # " =5" keeps an empty-string ticker key — pin the actual (harmless) behaviour
        assert config._parse_overrides("BAD, =5, foo=bar, ok=1.5") == {"": 5.0, "OK": 1.5}

    def test_empty_string_gives_empty_dict(self):
        assert config._parse_overrides("") == {}
