import unittest
from dependency_transport import adapt


class DependencyRepairs(unittest.TestCase):
    def test_uv_download_is_checked_before_extract_and_version_check(self):
        source = "RUN curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh\nENV PATH=\"/root/.local/bin:${PATH}\"\nRUN uv venv /opt/venv --python 3.11\n"
        rendered, changes = adapt(source)
        self.assertEqual(changes, ["uv-binary"])
        self.assertIn("download/0.9.7/", rendered)
        self.assertIn("-o /tmp/terminal-bench-uv.tar.gz && tar", rendered)
        self.assertIn("uv --version | grep -F 'uv 0.9.7'", rendered)
        self.assertTrue(rendered.endswith(source.split("\n", 1)[1]))

    def test_freecad_preserves_validator_and_existing_vtk(self):
        source = "RUN pip install --no-cache-dir 'gnucleus-freecad-validator[render]==0.1.3'\nCOPY . /tests/\n"
        rendered, changes = adapt(source)
        self.assertEqual(changes, ["vtk-compatible"])
        self.assertIn("'gnucleus-freecad-validator[render]==0.1.3' 'pyvista==0.46.4' 'vtk==9.2.6'", rendered)
        self.assertTrue(rendered.endswith("COPY . /tests/\n"))

    def test_healthy_uv_images_can_keep_their_cache(self):
        source = "RUN curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh\n"
        self.assertEqual(adapt(source, repair_uv=False), (source, []))

    def test_unrelated_sources_unchanged(self):
        source = "FROM ubuntu:22.04\nRUN curl https://example.com/install.sh | sh\n"
        self.assertEqual(adapt(source), (source, []))


if __name__ == '__main__':
    unittest.main()
