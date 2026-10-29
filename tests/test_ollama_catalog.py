import unittest
from unittest.mock import patch

import ollama_catalog as catalog


class OllamaCatalogTests(unittest.TestCase):
    def test_search_parses_only_catalog_model_links(self):
        html = '''<nav><a href="/library/not-a-result">navigation</a></nav>
        <ul><li><a href="/library/qwen3.5"><span>Qwen</span></a></li>
        <li><a href="/example/custom-model">custom</a></li>
        <li><a href="https://elsewhere.example/library/bad">bad</a></li>
        <li><a href="/library/qwen3.5">duplicate</a></li>
        <li><a href="/library/qwen3.5%3A4b">tag</a></li></ul>'''
        with patch.object(catalog, "_fetch", return_value=html) as fetch:
            self.assertEqual(catalog.search_models("qwen 3"), ["qwen3.5", "example/custom-model"])
            fetch.assert_called_once_with("/search?q=qwen+3")

    def test_tags_are_limited_to_selected_model(self):
        html = '''<a href="/library/gemma4%3Ae2b">E2B</a>
        <a href="/library/gemma4:12b">12b</a>
        <a href="/library/other:e2b">other</a>
        <a href="/library/gemma4:e2b">duplicate</a>'''
        with patch.object(catalog, "_fetch", return_value=html) as fetch:
            self.assertEqual(catalog.model_tags("gemma4"), ["gemma4:e2b", "gemma4:12b"])
            fetch.assert_called_once_with("/library/gemma4/tags")

    def test_namespace_and_unsafe_model_names(self):
        with patch.object(catalog, "_fetch", return_value='<a href="/user/model:4b">4b</a>') as fetch:
            self.assertEqual(catalog.model_tags("user/model"), ["user/model:4b"])
            fetch.assert_called_once_with("/user/model/tags")
        for name in ("-flag", "model;echo", "../../etc", "model:tag:bad"):
            self.assertIsNone(catalog.MODEL_PATTERN.fullmatch(name))
            with self.assertRaises(ValueError):
                catalog.model_tags(name)


if __name__ == "__main__":
    unittest.main()
