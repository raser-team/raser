"""Prepare Frontend ngspice transient and noise calculations."""

import re
from pathlib import Path

import ROOT


def _active_line(line):
    stripped = line.lstrip()
    return stripped and not stripped.startswith(("*", ";"))


def _line_startswith(line, keyword):
    if not _active_line(line):
        return False
    token = line.lstrip().split(None, 1)[0].lower().removeprefix(".")
    return token == keyword.lower()


def _line_has_onoise_spectrum(line):
    return _active_line(line) and "onoise_spectrum" in line.lower()


def _line_has_trnoise(line):
    return _active_line(line) and "trnoise" in line.lower()


def _replace_wrdata_path(line, raw):
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]
    tokens = stripped.split()
    if len(tokens) < 2 or tokens[0].lower() != "wrdata":
        return line
    return f"{indent}wrdata {raw} {' '.join(tokens[2:])}\n"


def _disable_trnoise_source(line):
    return re.sub(r"\bTRNOISE\s*\([^)]*\)", "0", line, flags=re.IGNORECASE)


def _replace_cdet_param(line, detector_capacitance_pF):
    if detector_capacitance_pF is None:
        return line
    return re.sub(
        r"^(\s*\.param\s+CDET\s*=\s*)\S+(.*)$",
        rf"\g<1>{float(detector_capacitance_pF):.12g}p\2",
        line,
        flags=re.IGNORECASE,
    )


def _resolve_include_path(line, circuit_path):
    if not _active_line(line):
        return line
    line_ending = line[len(line.rstrip("\r\n")) :]
    content = line[: -len(line_ending)] if line_ending else line
    match = re.match(
        r"^(\s*\.include\s+)(?:\"([^\"]+)\"|'([^']+)'|(\S+))(.*)$",
        content,
        flags=re.IGNORECASE,
    )
    if match is None:
        return line
    include_value = next(value for value in match.group(2, 3, 4) if value is not None)
    include_path = Path(include_value).expanduser()
    if include_path.is_absolute():
        return line
    resolved = (Path(circuit_path).resolve().parent / include_path).resolve()
    return f'{match.group(1)}"{resolved}"{match.group(5)}{line_ending}'


def circuit_has_noise_spectrum(circuit_path):
    has_noise = False
    has_output = False
    with open(circuit_path, encoding="utf-8") as stream:
        for line in stream:
            has_noise = has_noise or _line_startswith(line, "noise")
            has_output = has_output or _line_has_onoise_spectrum(line)
    return has_noise and has_output


def set_ngspice_input(currents: list[ROOT.TH1F]):
    values = []
    for histogram in currents:
        bin_count = histogram.GetNbinsX()
        bin_width = histogram.GetBinWidth(1)
        samples = [histogram.GetBinContent(index) for index in range(1, bin_count + 1)]
        times = [(index - 1) * bin_width for index in range(1, bin_count + 1)]
        if not samples:
            values.append("0,0")
            continue
        minimum = min(samples)
        maximum = max(samples)
        if minimum == 0.0 and maximum == 0.0:
            values.append(f"0,0,{times[-1]},0")
            continue

        if abs(minimum) > maximum:
            threshold = minimum * 0.01
            start = _first_index(samples, threshold, below=True)
            end_below = False
        else:
            threshold = maximum * 0.01
            start = _first_index(samples, threshold, below=False)
            end_below = True
        if start is None:
            values.append(f"0,0,{times[-1]},0")
            continue

        points = ["0", "0", str(times[start]), "0"]
        end = len(samples) - 1
        for index in range(start, len(samples)):
            points.extend((str(times[index]), str(samples[index])))
            if (samples[index] < threshold) == end_below:
                end = index
                break
        points.extend((str(times[end]), "0", str(times[-1]), "0"))
        values.append(",".join(points))
    return values


def _first_index(values, threshold, *, below):
    for index, value in enumerate(values):
        if (value < threshold) == below:
            return index
    return None


def set_tmp_cir(
    read_ele_num,
    path,
    input_current_strs,
    circuit_path,
    label=None,
    disable_trnoise=False,
    detector_capacitance_pF=None,
):
    label = label or ""
    tmp_cirs = []
    raws = []
    with open(circuit_path, encoding="utf-8") as stream:
        lines = stream.readlines()
    for channel in range(read_ele_num):
        input_current = input_current_strs[channel]
        if read_ele_num == 1:
            tmp_cir = f"{path}/{label}_tmp.cir"
            raw = f"{path}/{label}.raw"
        else:
            tmp_cir = f"{path}/{label}No.{channel}_tmp.cir"
            raw = f"{path}/{label}No.{channel}.raw"
        tmp_cirs.append(tmp_cir)
        raws.append(raw)

        output_lines = []
        for line in lines:
            line = _resolve_include_path(line, circuit_path)
            line = _replace_cdet_param(line, detector_capacitance_pF)
            if _line_startswith(line, "i1"):
                line = re.sub(
                    r"pulse.*",
                    f"PWL({input_current}) \n",
                    line,
                    flags=re.IGNORECASE,
                )
            if disable_trnoise and _line_has_trnoise(line):
                line = _disable_trnoise_source(line)
            if _line_startswith(line, "wrdata"):
                line = _replace_wrdata_path(line, raw)
            if (
                _line_startswith(line, "noise")
                or _line_startswith(line, "setplot")
                or _line_has_onoise_spectrum(line)
            ):
                line = "* skipped: " + line
            output_lines.append(line)
        with open(tmp_cir, "w", encoding="utf-8") as stream:
            stream.writelines(output_lines)
    return tmp_cirs, raws


def set_tmp_noise_cir(
    path,
    circuit_path,
    label=None,
    detector_capacitance_pF=None,
    disable_trnoise=False,
):
    label = label or ""
    tmp_cir = f"{path}/{label}_noise_tmp.cir"
    raw = f"{path}/{label}_noise.raw"
    with open(circuit_path, encoding="utf-8") as stream:
        lines = stream.readlines()

    has_noise = False
    has_output = False
    output_lines = []
    for line in lines:
        line = _resolve_include_path(line, circuit_path)
        line = _replace_cdet_param(line, detector_capacitance_pF)
        if disable_trnoise and _line_has_trnoise(line):
            line = _disable_trnoise_source(line)
        if _line_startswith(line, "noise"):
            has_noise = True
        elif _line_startswith(line, "tran"):
            line = "* skipped for noise spectrum: " + line
        elif _line_startswith(line, "wrdata"):
            if _line_has_onoise_spectrum(line):
                has_output = True
                line = _replace_wrdata_path(line, raw)
            else:
                line = "* skipped for noise spectrum: " + line
        output_lines.append(line)
    if not has_noise or not has_output:
        return None, None
    with open(tmp_cir, "w", encoding="utf-8") as stream:
        stream.writelines(output_lines)
    return tmp_cir, raw
