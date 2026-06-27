import ast
import os
import tempfile
import unittest

import numpy as np

from raser.afe.ngspice import circuit_has_noise_spectrum
from raser.afe.ngspice import set_ngspice_input
from raser.afe.ngspice import set_tmp_cir
from raser.afe.ngspice import set_tmp_noise_cir
from raser.afe.noise import estimate_noise_spectrum
from raser.afe.noise import integrate_noise_spectrum_rms
from raser.afe.noise import load_noise_spectrum
from raser.afe.noise import resolve_noise_spectrum_path
from raser.afe.noise import synthesize_noise_from_spectrum
from raser.afe.noise import write_noise_spectrum
from raser.afe.noise_estimation import build_noise_spectrum_config
from raser.afe.noise_estimation import collect_waveforms_from_root
from raser.afe.noise_estimation import estimate_spice_noise_spectrum
from raser.afe.noise_validation import validate_spectrum
from raser.afe.noise_validation import validate_waveforms


def read_readout_ast():
    readout_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "afe",
        "readout.py",
    )
    with open(readout_path) as handle:
        return ast.parse(handle.read())


class TestNoiseSpectrum(unittest.TestCase):
    def test_load_noise_spectrum_averages_duplicate_frequencies(self):
        handle = tempfile.NamedTemporaryFile("w", delete=False)
        try:
            with handle:
                handle.write("# frequency density\n")
                handle.write("10 6\n")
                handle.write("1 2\n")
                handle.write("not numeric\n")
                handle.write("1 4\n")

            frequencies, density = load_noise_spectrum(handle.name)

            np.testing.assert_allclose(frequencies, [1.0, 10.0])
            np.testing.assert_allclose(density, [3.0, 6.0])
        finally:
            os.remove(handle.name)

    def test_relative_spectrum_path_prefers_config_directory(self):
        with tempfile.TemporaryDirectory() as cwd:
            with tempfile.TemporaryDirectory() as base_dir:
                name = "noise.raw"
                cwd_path = os.path.join(cwd, name)
                base_path = os.path.join(base_dir, name)
                with open(cwd_path, "w") as handle:
                    handle.write("1 1\n2 2\n")
                with open(base_path, "w") as handle:
                    handle.write("1 3\n2 4\n")

                previous_cwd = os.getcwd()
                try:
                    os.chdir(cwd)
                    resolved = resolve_noise_spectrum_path(name, base_dir)
                finally:
                    os.chdir(previous_cwd)

                self.assertEqual(resolved, base_path)

    def test_estimate_noise_spectrum_recovers_baseline_rms(self):
        rng = np.random.default_rng(12345)
        target_rms = 0.4
        time_step_s = 1.0e-9
        waveforms = rng.normal(0.0, target_rms, size=(12, 4096))

        frequencies, psd = estimate_noise_spectrum(
            waveforms,
            time_step_s,
            segment_length=1024,
            overlap=0.5,
            density_type="power",
        )

        df = frequencies[1] - frequencies[0]
        estimated_rms = float(np.sqrt(np.sum(psd) * df))
        self.assertAlmostEqual(estimated_rms, target_rms, delta=0.04)

    def test_estimated_spectrum_can_be_written_and_sampled(self):
        rng = np.random.default_rng(6789)
        target_rms = 0.25
        time_step_s = 2.0e-9
        waveforms = rng.normal(0.0, target_rms, size=(8, 4096))

        frequencies, density = estimate_noise_spectrum(
            waveforms,
            time_step_s,
            segment_length=1024,
            overlap=0.5,
            density_type="amplitude",
        )

        handle = tempfile.NamedTemporaryFile("w", delete=False)
        try:
            handle.close()
            write_noise_spectrum(handle.name, frequencies, density)
            loaded_frequencies, loaded_density = load_noise_spectrum(handle.name)
        finally:
            os.remove(handle.name)

        noise = synthesize_noise_from_spectrum(
            loaded_frequencies,
            loaded_density,
            4096,
            time_step_s,
            seed=2468,
        )

        self.assertAlmostEqual(float(np.std(noise)), target_rms, delta=0.06)

    def test_validate_waveforms_compares_resampled_noise(self):
        rng = np.random.default_rng(13579)
        waveforms = rng.normal(0.0, 0.3, size=(10, 2048))

        metrics, _ = validate_waveforms(
            waveforms,
            1.0e-9,
            segment_length=512,
            n_synthetic=12,
            seed=123,
        )

        self.assertEqual(metrics["n_measured_waveforms"], 10)
        self.assertEqual(metrics["n_synthetic_waveforms"], 12)
        self.assertLess(abs(metrics["rms_relative_difference"]), 0.25)
        self.assertLess(metrics["asd_log10_ratio_rms"], 0.25)

    def test_validate_spectrum_self_consistency(self):
        frequencies = np.array([0.0, 5.0e8], dtype=np.float64)
        density = np.array([1.0e-5, 1.0e-5], dtype=np.float64)

        metrics, _ = validate_spectrum(
            frequencies,
            density,
            2048,
            1.0e-9,
            segment_length=512,
            n_synthetic=16,
            seed=456,
        )

        self.assertEqual(metrics["n_synthetic_waveforms"], 16)
        self.assertIn("reference_rms", metrics)
        self.assertLess(abs(metrics["asd_log10_ratio_mean"]), 0.2)
        self.assertLess(metrics["asd_log10_ratio_rms"], 0.35)

    def test_integrate_noise_spectrum_rms_respects_scale_and_cutoff(self):
        frequencies = np.array([0.0, 1.0e9, 2.0e9], dtype=np.float64)
        density = np.array([1.0e-9, 1.0e-9, 1.0e-9], dtype=np.float64)

        rms = integrate_noise_spectrum_rms(
            frequencies,
            density,
            unit_scale=1000.0,
            max_frequency_hz=1.0e9,
        )

        self.assertAlmostEqual(rms, np.sqrt(1.0e-3), places=12)

    def test_validate_spectrum_applies_configured_rms(self):
        frequencies = np.array([0.0, 5.0e8], dtype=np.float64)
        density = np.array([1.0e-9, 1.0e-9], dtype=np.float64)

        metrics, _ = validate_spectrum(
            frequencies,
            density,
            4096,
            1.0e-9,
            unit_scale=1000.0,
            target_rms=0.25,
            segment_length=512,
            n_synthetic=16,
            seed=789,
        )

        self.assertAlmostEqual(metrics["synthetic_rms_mean"], 0.25, delta=0.03)
        self.assertLess(metrics["asd_log10_ratio_rms"], 0.35)

    def test_validate_spectrum_respects_min_frequency_cutoff(self):
        frequencies = np.array([0.0, 1.0e9], dtype=np.float64)
        density = np.array([1.0e-6, 1.0e-6], dtype=np.float64)

        metrics, _ = validate_spectrum(
            frequencies,
            density,
            4096,
            1.0e-9,
            min_frequency_hz=4.0e8,
            segment_length=512,
            n_synthetic=48,
            seed=246,
        )

        self.assertAlmostEqual(
            metrics["synthetic_rms_mean"],
            metrics["reference_rms"],
            delta=0.1 * metrics["reference_rms"],
        )

    def test_collect_top_level_root_histogram_for_estimation(self):
        import ROOT

        handle = tempfile.NamedTemporaryFile(suffix=".root", delete=False)
        handle.close()
        try:
            root_file = ROOT.TFile(handle.name, "RECREATE")
            hist = ROOT.TH1F("electronics_mV", "electronics_mV", 4, 0.0, 4.0e-9)
            for index, value in enumerate([1.0, 2.0, 3.0, 4.0], start=1):
                hist.SetBinContent(index, value)
            hist.Write()
            root_file.Close()

            waveforms, time_step, sources = collect_waveforms_from_root(
                handle.name,
                tree_name="none",
            )

            np.testing.assert_allclose(waveforms, [[1.0, 2.0, 3.0, 4.0]])
            self.assertAlmostEqual(time_step, 1.0e-9)
            self.assertEqual(sources, ["electronics_mV"])
        finally:
            os.remove(handle.name)

    def test_collect_directory_scan_ignores_non_waveform_histograms(self):
        import ROOT

        handle = tempfile.NamedTemporaryFile(suffix=".root", delete=False)
        handle.close()
        try:
            root_file = ROOT.TFile(handle.name, "RECREATE")
            hist2 = ROOT.TH2F("map", "map", 2, 0.0, 2.0, 2, 0.0, 2.0)
            hist2.Write()
            hist1 = ROOT.TH1F("baseline", "baseline", 3, 0.0, 3.0e-9)
            for index, value in enumerate([0.1, 0.2, 0.3], start=1):
                hist1.SetBinContent(index, value)
            hist1.Write()
            root_file.Close()

            waveforms, _, sources = collect_waveforms_from_root(
                handle.name,
                tree_name=None,
            )

            np.testing.assert_allclose(waveforms, [[0.1, 0.2, 0.3]])
            self.assertEqual(sources, ["baseline"])
        finally:
            os.remove(handle.name)

    def test_collect_canvas_embedded_histogram_for_estimation(self):
        import ROOT

        handle = tempfile.NamedTemporaryFile(suffix=".root", delete=False)
        handle.close()
        try:
            root_file = ROOT.TFile(handle.name, "RECREATE")
            canvas = ROOT.TCanvas("c", "c")
            hist = ROOT.TH1F("canvas_waveform", "canvas_waveform", 4, 0.0, 8.0e-9)
            for index, value in enumerate([0.4, 0.3, 0.2, 0.1], start=1):
                hist.SetBinContent(index, value)
            hist.Draw()
            canvas.Write()
            root_file.Close()

            waveforms, time_step, sources = collect_waveforms_from_root(
                handle.name,
                tree_name=None,
            )

            np.testing.assert_allclose(waveforms, [[0.4, 0.3, 0.2, 0.1]])
            self.assertAlmostEqual(time_step, 2.0e-9)
            self.assertEqual(sources, ["c/canvas_waveform"])
        finally:
            os.remove(handle.name)

    def test_auto_collect_prefers_electronics_histogram_in_canvas(self):
        import ROOT

        handle = tempfile.NamedTemporaryFile(suffix=".root", delete=False)
        handle.close()
        try:
            root_file = ROOT.TFile(handle.name, "RECREATE")
            canvas = ROOT.TCanvas("c", "c")
            frame = ROOT.TH1F("hframe", "hframe", 2, 0.0, 2.0e-9)
            current = ROOT.TH1F("current", "current", 2, 0.0, 2.0e-9)
            electronics = ROOT.TH1F(
                "electronics Broad_Band1",
                "electronics Broad_Band1",
                4,
                0.0,
                4.0e-9,
            )
            for index, value in enumerate([0.4, 0.3, 0.2, 0.1], start=1):
                electronics.SetBinContent(index, value)
            frame.Draw()
            current.Draw("SAME")
            electronics.Draw("SAME")
            canvas.Write()
            root_file.Close()

            waveforms, time_step, sources = collect_waveforms_from_root(
                handle.name,
                tree_name=None,
            )

            np.testing.assert_allclose(waveforms, [[0.4, 0.3, 0.2, 0.1]])
            self.assertAlmostEqual(time_step, 1.0e-9)
            self.assertEqual(sources, ["c/electronics Broad_Band1"])
        finally:
            os.remove(handle.name)

    def test_collect_tree_histogram_branch_for_estimation(self):
        import ROOT

        handle = tempfile.NamedTemporaryFile(suffix=".root", delete=False)
        handle.close()
        try:
            root_file = ROOT.TFile(handle.name, "RECREATE")
            tree = ROOT.TTree("tree", "baseline")
            hist = ROOT.TH1F("amplified_waveform_0", "amplified_waveform_0", 3, 0.0, 3.0e-9)
            tree.Branch("amplified_waveform_0", hist)
            for event in range(2):
                hist.Reset()
                for index in range(1, 4):
                    hist.SetBinContent(index, event + index)
                tree.Fill()
            tree.Write()
            root_file.Close()

            waveforms, time_step, sources = collect_waveforms_from_root(
                handle.name,
                branches=["amplified_waveform_0"],
            )

            np.testing.assert_allclose(waveforms, [[1.0, 2.0, 3.0], [2.0, 3.0, 4.0]])
            self.assertAlmostEqual(time_step, 1.0e-9)
            self.assertEqual(
                sources,
                ["tree.amplified_waveform_0[0]", "tree.amplified_waveform_0[1]"],
            )
        finally:
            os.remove(handle.name)

    def test_build_noise_spectrum_config_uses_spectrum_file_only(self):
        config = build_noise_spectrum_config(
            "/tmp/example_noise.raw",
            density_type="amplitude",
            target_rms=0.25,
            max_frequency_hz=5.0e9,
        )

        self.assertEqual(config["file"], "example_noise.raw")
        self.assertEqual(config["density_type"], "amplitude")
        self.assertEqual(config["target_rms"], 0.25)
        self.assertEqual(config["max_frequency_hz"], 5.0e9)
        self.assertNotIn("white_noise_rms", config)
        self.assertNotIn("baseline_rms", config)

    def test_build_noise_spectrum_config_does_not_force_target_rms(self):
        config = build_noise_spectrum_config(
            "/tmp/example_noise.raw",
            density_type="amplitude",
            max_frequency_hz=1.0e9,
        )

        self.assertEqual(config["max_frequency_hz"], 1.0e9)
        self.assertNotIn("target_rms", config)

    def test_build_noise_spectrum_config_uses_config_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = os.path.join(directory, "electronics")
            spectrum_path = os.path.join(config_dir, "estimated", "noise.raw")
            config = build_noise_spectrum_config(
                spectrum_path,
                density_type="amplitude",
                config_dir=config_dir,
            )

            self.assertEqual(config["file"], os.path.join("estimated", "noise.raw"))

    def test_amplifier_default_seed_uses_random_mode(self):
        module = read_readout_ast()

        default_seed = None
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                arg_names = [arg.arg for arg in node.args.args]
                seed_index = arg_names.index("seed")
                default_index = seed_index - (len(arg_names) - len(node.args.defaults))
                default_seed = node.args.defaults[default_index]
                break

        self.assertIsInstance(default_seed, ast.Constant)
        self.assertIsNone(default_seed.value)

    def test_gaussian_fallback_accepts_random_mode_seed(self):
        module = read_readout_ast()

        set_seed_arg = None
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef) and node.name == "add_noise":
                for child in ast.walk(node):
                    if (
                        isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Attribute)
                        and child.func.attr == "SetSeed"
                    ):
                        set_seed_arg = child.args[0]
                        break
                break

        self.assertIsInstance(set_seed_arg, ast.IfExp)
        self.assertIsInstance(set_seed_arg.test, ast.Compare)
        self.assertIsInstance(set_seed_arg.test.left, ast.Name)
        self.assertEqual(set_seed_arg.test.left.id, "seed")
        self.assertIsInstance(set_seed_arg.test.ops[0], ast.Is)
        self.assertIsNone(set_seed_arg.test.comparators[0].value)
        self.assertEqual(set_seed_arg.body.value, 0)

    def test_spectrum_noise_is_reproducible_and_normalized(self):
        frequencies = np.array([1.0, 1.0e9], dtype=np.float64)
        amplitude_density = np.array([1.0e-3, 1.0e-3], dtype=np.float64)

        noise_a = synthesize_noise_from_spectrum(
            frequencies,
            amplitude_density,
            1024,
            1.0e-9,
            seed=123,
            mean=0.1,
            target_rms=0.5,
        )
        noise_b = synthesize_noise_from_spectrum(
            frequencies,
            amplitude_density,
            1024,
            1.0e-9,
            seed=123,
            mean=0.1,
            target_rms=0.5,
        )

        np.testing.assert_allclose(noise_a, noise_b)
        self.assertAlmostEqual(float(np.mean(noise_a)), 0.1, places=12)
        self.assertAlmostEqual(float(np.std(noise_a)), 0.5, places=12)

    def test_min_frequency_cutoff_removes_spectrum_component(self):
        frequencies = np.array([1.0, 1.0e6], dtype=np.float64)
        amplitude_density = np.array([1.0, 1.0], dtype=np.float64)

        noise = synthesize_noise_from_spectrum(
            frequencies,
            amplitude_density,
            1024,
            1.0e-9,
            seed=123,
            min_frequency_hz=2.0e9,
        )

        np.testing.assert_allclose(noise, np.zeros_like(noise))

    def test_spectrum_is_not_extrapolated_below_lowest_frequency(self):
        frequencies = np.array([10.0, 20.0], dtype=np.float64)
        amplitude_density = np.array([1.0, 1.0], dtype=np.float64)

        noise = synthesize_noise_from_spectrum(
            frequencies,
            amplitude_density,
            1024,
            0.1,
            seed=456,
        )

        np.testing.assert_allclose(noise, np.zeros_like(noise))


class TestNgspiceNoiseSetup(unittest.TestCase):
    def test_set_ngspice_input_preserves_positive_current_pulse(self):
        import ROOT

        hist = ROOT.TH1F("positive_current", "positive_current", 10, 0.0, 10.0e-9)
        hist.SetDirectory(0)
        for index in range(4, 7):
            hist.SetBinContent(index, 1.0e-6)

        pwl = set_ngspice_input([hist])[0]
        tokens = [float(token) for token in pwl.split(",")]
        values = tokens[1::2]

        self.assertEqual(tokens[0], 0.0)
        self.assertEqual(tokens[1], 0.0)
        self.assertGreater(max(values), 0.0)

    def test_set_ngspice_input_uses_histogram_bins_not_underflow(self):
        import ROOT

        hist = ROOT.TH1F("last_bin_current", "last_bin_current", 3, 0.0, 3.0e-9)
        hist.SetDirectory(0)
        hist.SetBinContent(3, 2.0e-6)

        pwl = set_ngspice_input([hist])[0]
        tokens = [float(token) for token in pwl.split(",")]
        values = tokens[1::2]

        self.assertGreater(max(values), 0.0)

    def write_circuit(self, directory, text):
        path = os.path.join(directory, "amp.cir")
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def test_circuit_has_noise_spectrum_detects_active_noise_output(self):
        with tempfile.TemporaryDirectory() as directory:
            cir = self.write_circuit(
                directory,
                "\n".join([
                    "I1 0 in PULSE(0 1u 0 1p 1p 1n 2n)",
                    ".control",
                    ".noise v(out) V1 dec 10 1Hz 1GHz",
                    "setplot noise1",
                    "wrdata noise.raw onoise_spectrum",
                    ".endc",
                ]),
            )

            self.assertTrue(circuit_has_noise_spectrum(cir))

    def test_set_tmp_cir_keeps_trnoise_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            cir = self.write_circuit(
                directory,
                "\n".join([
                    "V8 in out TRNOISE( 10m 10p 0 0 0 0 0 ) AC 0 0",
                    "I1 0 in PULSE(0 1u 0 1p 1p 1n 2n)",
                    ".control",
                    "tran 0.1n 10n",
                    "wrdata old.raw v(out)",
                    ".endc",
                ]),
            )

            tmp_cirs, _ = set_tmp_cir(1, directory, ["0,0"], cir, "keep")

            with open(tmp_cirs[0]) as handle:
                self.assertIn("TRNOISE", handle.read())

    def test_set_tmp_cir_replaces_only_i1_source(self):
        with tempfile.TemporaryDirectory() as directory:
            cir = self.write_circuit(
                directory,
                "\n".join([
                    "I1 0 in PULSE(0 1u 0 1p 1p 1n 2n)",
                    "I10 0 aux PULSE(0 2u 0 1p 1p 1n 2n)",
                    ".control",
                    "tran 0.1n 10n",
                    "wrdata old.raw v(out)",
                    ".endc",
                ]),
            )

            tmp_cirs, _ = set_tmp_cir(1, directory, ["0,0"], cir, "i1_only")

            with open(tmp_cirs[0]) as handle:
                text = handle.read()
            self.assertIn("I1 0 in PWL(0,0)", text)
            self.assertIn("I10 0 aux PULSE", text)

    def test_set_tmp_cir_can_disable_trnoise(self):
        with tempfile.TemporaryDirectory() as directory:
            cir = self.write_circuit(
                directory,
                "\n".join([
                    "V8 in out TRNOISE( 10m 10p 0 0 0 0 0 ) AC 0 0",
                    "I1 0 in PULSE(0 1u 0 1p 1p 1n 2n)",
                    ".control",
                    "tran 0.1n 10n",
                    "wrdata old.raw v(out)",
                    ".endc",
                ]),
            )

            tmp_cirs, _ = set_tmp_cir(
                1,
                directory,
                ["0,0"],
                cir,
                "disable",
                disable_trnoise=True,
            )

            with open(tmp_cirs[0]) as handle:
                text = handle.read()
            self.assertNotIn("TRNOISE", text)
            self.assertIn("V8 in out 0 AC 0 0", text)

    def test_set_tmp_noise_cir_keeps_only_noise_output(self):
        with tempfile.TemporaryDirectory() as directory:
            cir = self.write_circuit(
                directory,
                "\n".join([
                    "I1 0 in PULSE(0 1u 0 1p 1p 1n 2n)",
                    ".control",
                    "noise v(out) I1 dec 10 1Hz 1GHz",
                    "setplot noise1",
                    "wrdata transient.raw v(out)",
                    "wrdata noise.raw onoise_spectrum",
                    "tran 0.1n 10n",
                    ".endc",
                ]),
            )

            tmp_cir, raw = set_tmp_noise_cir(directory, cir, "noise_only")

            with open(tmp_cir) as handle:
                text = handle.read()
            self.assertIn("noise v(out) I1", text)
            self.assertIn("wrdata {} onoise_spectrum".format(raw), text)
            self.assertIn("* skipped for noise spectrum: tran", text)
            self.assertIn("* skipped for noise spectrum: wrdata transient.raw", text)

    def test_estimate_spice_noise_spectrum_writes_output(self):
        with tempfile.TemporaryDirectory() as directory:
            cir = self.write_circuit(
                directory,
                "\n".join([
                    "I1 0 in PULSE(0 1u 0 1p 1p 1n 2n) AC 1",
                    ".control",
                    "noise v(out) I1 dec 10 1Hz 1GHz",
                    "setplot noise1",
                    "wrdata old.raw onoise_spectrum",
                    ".endc",
                ]),
            )
            fake_ngspice = os.path.join(directory, "fake_ngspice.py")
            with open(fake_ngspice, "w") as handle:
                handle.write(
                    "#!/usr/bin/env python3\n"
                    "import sys\n"
                    "with open(sys.argv[-1]) as circuit:\n"
                    "    for line in circuit:\n"
                    "        parts = line.split()\n"
                    "        if parts[:1] == ['wrdata']:\n"
                    "            with open(parts[1], 'w') as output:\n"
                    "                output.write('1.0e+00 2.0e-09\\n')\n"
                    "                output.write('1.0e+09 2.0e-09\\n')\n"
                    "            break\n"
                )
            os.chmod(fake_ngspice, 0o755)
            output_path = os.path.join(directory, "estimated.raw")

            frequencies, density, return_code = estimate_spice_noise_spectrum(
                cir,
                output_path,
                ngspice_executable=fake_ngspice,
                work_dir=directory,
            )

            self.assertEqual(return_code, 0)
            self.assertTrue(os.path.exists(output_path))
            np.testing.assert_allclose(frequencies, [1.0, 1.0e9])
            np.testing.assert_allclose(density, [2.0e-9, 2.0e-9])


if __name__ == "__main__":
    unittest.main()
