"""Combinational logic simulator producing WaveDrom JSON."""

import sys
import argparse
from pathlib import Path
from typing import List

def parse_netlsit(text_data: str):
    lines_cleaned = []
    for raw_line in text_data.splitlines():
        raw_line = raw_line.strip()
        if not raw_line or raw_line.startswith("#"):
            continue
        lines_cleaned.append(raw_line)

    def locate_section(section_name):
        for idx, content in enumerate(lines_cleaned):
            if content.startswith(section_name + ":"):
                return idx
        raise ValueError(f"Missing section: {section_name}")

    idx_outputs = locate_section("OUTPUTS")
    idx_gates = locate_section("GATES")
    idx_inputs = locate_section("INPUTS")
    idx_stimulus = locate_section("STIMULUS")

    input_signals = lines_cleaned[idx_inputs].split(":", 1)[1].split()
    output_signals = lines_cleaned[idx_outputs].split(":", 1)[1].split()

    logic_blocks = []
    for content in lines_cleaned[idx_gates + 1 : idx_stimulus]:
        if content.startswith("#") or not content:
            continue
        lhs, rhs = content.split("=")
        out_sig = lhs.strip()
        gate_kind = rhs.split("(")[0].strip()
        params = rhs.split("(")[1].split(")")[0].split(",")
        params = [p.strip() for p in params]
        logic_blocks.append((out_sig, gate_kind, params))

    stimuli_data = []
    for content in lines_cleaned[idx_stimulus + 1 :]:
        tokens = content.split()
        if not tokens:
            continue
        timestamp = int(tokens[0])
        values = [int(x) for x in tokens[1:]]
        if len(values) != len(input_signals):
            raise ValueError(f"Stimulus line mismatch: {content}")
        stimuli_data.append((timestamp, values))

    times_list = [t for t, _ in stimuli_data]
    if times_list != sorted(set(times_list)):
        raise ValueError("Times not strictly increasing")

    return {
        "inputs": input_signals,
        "outputs": output_signals,
        "gates": logic_blocks,
        "stimulus": stimuli_data,
    }

def eval_gate(gate_kind: str, args: List[int]):
    if gate_kind == "AND":
        return args[0] & args[1]
    elif gate_kind == "OR":
        return args[0] | args[1]
    elif gate_kind == "NOT":
        return 1 - args[0]
    elif gate_kind == "XOR":
        return args[0] ^ args[1]
    else:
        raise ValueError(f"Unknown gate type {gate_kind}")

def simulate(circuit: dict) -> dict[str, List[int]]:
    input_signals = circuit["inputs"]
    output_signals = circuit["outputs"]
    logic_blocks = circuit["gates"]
    stimuli_data = circuit["stimulus"]

    all_nodes = set(input_signals) | {g[0] for g in logic_blocks} | set(output_signals)
    waveform_map = {n: [] for n in all_nodes}

    for _, input_values in stimuli_data:
        signal_env = dict(zip(input_signals, input_values))
        changed_flag = True

        while changed_flag:
            changed_flag = False
            for dest, kind, params in logic_blocks:
                if dest in signal_env:
                    continue
                if all(p in signal_env for p in params):
                    signal_env[dest] = eval_gate(kind, [signal_env[p] for p in params])
                    changed_flag = True

        for sig in input_signals + output_signals:
            waveform_map[sig].append(signal_env.get(sig, 0))

    return waveform_map

def to_wavedrom_json(circuit: dict, wave_data: dict[str, List[int]]) -> str:
    output_lines = ['{', '  "signal": [']
    all_signals = circuit["inputs"] + circuit["outputs"]

    for idx, sig in enumerate(all_signals):
        wave_str = "".join(str(x) for x in wave_data[sig])
        comma = "," if idx < len(all_signals) - 1 else ""
        output_lines.append(f'    {{ "name": "{sig}", "wave": "{wave_str}" }}{comma}')

    output_lines.append("  ]")
    output_lines.append("}")
    return "\n".join(output_lines)

def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("net_file", help=".net file path")
    parser.add_argument("--out", "-o", help="output JSON path")
    args = parser.parse_args(argv)

    file_content = Path(args.net_file).read_text()
    circuit = parse_netlsit(file_content)
    waveforms = simulate(circuit)
    json_output = to_wavedrom_json(circuit, waveforms)

    output_path = args.out
    if not output_path:
        p = Path(args.net_file)
        output_path = str(p.with_suffix(".json"))
    Path(output_path).write_text(json_output + "\n")
    print(output_path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
