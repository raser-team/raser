'''
Description:
    Simulate induced current through NGSpice

@Date       : 2023
@Author     : Ye He, Kaibo Xie, Yanpeng Li
@version    : 2.0
'''

import re

import ROOT


def _active_line(line):
    stripped = line.lstrip()
    return stripped and not stripped.startswith(("*", ";"))


def _line_startswith(line, keyword):
    if not _active_line(line):
        return False
    token = line.lstrip().split(None, 1)[0].lower()
    if token.startswith("."):
        token = token[1:]
    return token == keyword.lower()


def _line_has_onoise_spectrum(line):
    return _active_line(line) and "onoise_spectrum" in line.lower()


def _line_has_trnoise(line):
    return _active_line(line) and "trnoise" in line.lower()


def _replace_wrdata_path(line, raw):
    stripped = line.lstrip()
    indent = line[:len(line) - len(stripped)]
    tokens = stripped.split()
    if len(tokens) < 2 or tokens[0].lower() != "wrdata":
        return line
    return "{}wrdata {} {}\n".format(indent, raw, " ".join(tokens[2:]))


def _disable_trnoise_source(line):
    return re.sub(
        r"\bTRNOISE\s*\([^)]*\)",
        "0",
        line,
        flags=re.IGNORECASE,
    )


def circuit_has_noise_spectrum(ele_cir):
    has_noise = False
    has_onoise_spectrum = False
    with open(ele_cir, 'r') as f_in:
        for line in f_in:
            if _line_startswith(line, 'noise'):
                has_noise = True
            if _line_has_onoise_spectrum(line):
                has_onoise_spectrum = True
    return has_noise and has_onoise_spectrum


def set_ngspice_input(currents: list[ROOT.TH1F]):
    input_current_strs = []
    for th1fcu in currents:
        n_bins = th1fcu.GetNbinsX()
        bin_width = th1fcu.GetBinWidth(1)
        current = [
            th1fcu.GetBinContent(bin_index)
            for bin_index in range(1, n_bins + 1)
        ]
        time = [
            (bin_index - 1) * bin_width
            for bin_index in range(1, n_bins + 1)
        ]

        if not current:
            input_current_strs.append("0,0")
            continue

        min_current = min(current)
        max_current = max(current)
        if min_current == 0.0 and max_current == 0.0:
            input_current_strs.append(
                "{},{},{},{}".format(0, 0, time[-1], 0)
            )
            continue

        input_c = [str(0), str(0)]
        if abs(min_current) > max_current:
            threshold = min_current * 0.01
            start_index = _first_index(current, lambda value: value < threshold)
            end_condition = lambda value: value > threshold
        else:
            threshold = max_current * 0.01
            start_index = _first_index(current, lambda value: value > threshold)
            end_condition = lambda value: value < threshold

        if start_index is None:
            input_current_strs.append(
                "{},{},{},{}".format(0, 0, time[-1], 0)
            )
            continue

        input_c.extend([str(time[start_index]), str(0)])
        end_index = len(current) - 1
        for index in range(start_index, len(current)):
            input_c.extend([str(time[index]), str(current[index])])
            if end_condition(current[index]):
                end_index = index
                break

        input_c.extend([str(time[end_index]), str(0)])
        input_c.extend([str(time[-1]), str(0)])

        input_current_strs.append(','.join(input_c))
    return input_current_strs


def _first_index(values, predicate):
    for index, value in enumerate(values):
        if predicate(value):
            return index
    return None


def set_tmp_cir(read_ele_num, path, input_current_strs, ele_cir, label=None, disable_trnoise=False):
    if label is None:
        label = ''
    tmp_cirs = []
    raws = []
    with open(ele_cir, 'r') as f_in:
        lines = f_in.readlines()
        for j in range(read_ele_num):
            new_lines = lines.copy()
            input_c = input_current_strs[j]
            if read_ele_num==1:
                tmp_cir = "{}/{}_tmp.cir".format(path, label)
                raw = "{}/{}.raw".format(path, label)
            else:
                tmp_cir = '{}/{}{}_tmp.cir'.format(path, label, "No."+str(j))
                raw = '{}/{}{}.raw'.format(path, label, "No."+str(j))

            tmp_cirs.append(tmp_cir)
            raws.append(raw)

            for i in range(len(new_lines)):
                if _line_startswith(new_lines[i], 'i1'):
                    # replace pulse by PWL
                    new_lines[i] = re.sub(
                        r"pulse" + r".*",
                        'PWL(' + str(input_c) + ') \n',
                        new_lines[i],
                        flags=re.IGNORECASE,
                    )
                if disable_trnoise and _line_has_trnoise(new_lines[i]):
                    new_lines[i] = _disable_trnoise_source(new_lines[i])
                if _line_startswith(new_lines[i], 'wrdata'):
                    # replace output file name & path
                    new_lines[i] = _replace_wrdata_path(new_lines[i], raw)
                if (
                    _line_startswith(new_lines[i], 'noise')
                    or _line_startswith(new_lines[i], 'setplot')
                    or _line_has_onoise_spectrum(new_lines[i])
                ):
                    # skip noise spectrum calculation
                    new_lines[i] = '* skipped: ' + new_lines[i]
            with open(tmp_cir, 'w') as f_out:
                f_out.writelines(new_lines)

    return tmp_cirs, raws


def set_tmp_noise_cir(path, ele_cir, label=None):
    if label is None:
        label = ''

    tmp_cir = "{}/{}_noise_tmp.cir".format(path, label)
    raw = "{}/{}_noise.raw".format(path, label)
    has_noise = False
    has_onoise_spectrum = False

    with open(ele_cir, 'r') as f_in:
        lines = f_in.readlines()

    new_lines = []
    for line in lines:
        if _line_startswith(line, 'noise'):
            has_noise = True
            new_lines.append(line)
        elif _line_startswith(line, 'tran'):
            new_lines.append('* skipped for noise spectrum: ' + line)
        elif _line_startswith(line, 'wrdata'):
            if _line_has_onoise_spectrum(line):
                has_onoise_spectrum = True
                new_lines.append(_replace_wrdata_path(line, raw))
            else:
                new_lines.append('* skipped for noise spectrum: ' + line)
        else:
            new_lines.append(line)

    if not has_noise or not has_onoise_spectrum:
        return None, None

    with open(tmp_cir, 'w') as f_out:
        f_out.writelines(new_lines)

    return tmp_cir, raw
