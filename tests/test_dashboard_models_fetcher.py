import unittest
from dashboard.models_fetcher import get_available_models_for_provider, fetch_gemini_models, DEFAULT_GEMINI_MODELS


class TestDashboardModelsFetcher(unittest.TestCase):
    def test_default_models_fallback_when_no_key(self):
        models = fetch_gemini_models(api_key="")
        self.assertGreaterEqual(len(models), 3)
        ids = [m[1] for m in models]
        self.assertIn("gemini-2.5-flash", ids)
        self.assertIn("gemini-2.0-flash", ids)

    def test_provider_router(self):
        openai_models = get_available_models_for_provider("openai")
        self.assertTrue(any("gpt-4o" in m[1] for m in openai_models))

        lmstudio_models = get_available_models_for_provider("lmstudio")
        self.assertTrue(len(lmstudio_models) >= 1)
