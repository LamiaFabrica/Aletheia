# Run this script as a module from the tool_crawler directory:
#   python -m parsers.demo_kali_parser_run

from .plugins.BinMan_RubbishRecycler import BinMan_RubbishRecycler
import os

SAMPLES = [
    ('aircrack_ng_sample.html', 'https://www.aircrack-ng.org/'),
    ('metasploit_sample.html', 'https://docs.metasploit.com/')
]

def load_html(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_output(filename, content):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(base_dir, filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)

error_files_list = []

def main():
    print("--- Demo Script Started ---")
    try:
        parser = BinMan_RubbishRecycler()
        print(f"  INFO: BinMan_RubbishRecycler instantiated successfully: {type(parser)}")
    except Exception as e:
        print(f"  ERROR: Failed to instantiate BinMan_RubbishRecycler: {e}")
        import traceback
        traceback.print_exc()
        print("--- Demo Script Finished Due to Parser Instantiation Error ---")
        return

    if not SAMPLES:
        print("  INFO: No samples defined in SAMPLES list.")
        print("--- Demo Script Finished ---")
        return

    for fname, url in SAMPLES:
        output_lines = []
        output_lines.append(f'=== Processing sample: {fname} (URL: {url}) ===')
        html_content = None
        try:
            html_content = load_html(fname)
            output_lines.append(f"  INFO: Successfully loaded HTML for {fname} (length: {len(html_content)} chars)")
        except FileNotFoundError:
            expected_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
            output_lines.append(f'  ERROR: File not found: {expected_path}')
            error_files_list.append(f"{fname} (File Not Found at {expected_path})")
            write_output(fname.replace('.html', '_output.txt'), '\n'.join(output_lines))
            continue
        except Exception as e:
            output_lines.append(f"  ERROR: Could not load HTML for {fname}: {e}")
            import traceback
            import io
            buf = io.StringIO()
            traceback.print_exc(file=buf)
            output_lines.append(buf.getvalue())
            error_files_list.append(f"{fname} (Error loading HTML: {e})")
            write_output(fname.replace('.html', '_output.txt'), '\n'.join(output_lines))
            continue

        if html_content is None:
            output_lines.append(f"  ERROR: HTML content is None for {fname} after load attempt.")
            write_output(fname.replace('.html', '_output.txt'), '\n'.join(output_lines))
            continue

        response_obj = {'content': html_content, 'url': url, 'file_name': fname}
        try:
            output_lines.append(f"  STEP: Calling parser.can_parse() for {fname}...")
            can_parse_result = parser.can_parse(response_obj)
            output_lines.append(f"  RESULT: parser.can_parse() returned: {can_parse_result}")

            if can_parse_result:
                output_lines.append(f"  STEP: Calling parser.parse() for {fname}...")
                results = parser.parse(response_obj)
                if results is None:
                    output_lines.append("  RESULT: parser.parse() returned None. No tools extracted or error in parser.")
                elif isinstance(results, list):
                    output_lines.append(f"  RESULT: parser.parse() returned a list with {len(results)} item(s).")
                    if not results:
                        output_lines.append("  INFO: Parser.parse() returned an empty list - no tools extracted.")
                    for i, tool_data_dict in enumerate(results):
                        output_lines.append(f'    --- Tool #{i+1} Extracted from {fname} ---')
                        if isinstance(tool_data_dict, dict):
                            for k, v in tool_data_dict.items():
                                v_str = str(v)
                                output_lines.append(f'      {k}: {v_str[:150]}{"..." if len(v_str) > 150 else ""}')
                            missing = [k for k, v in tool_data_dict.items() if v is None]
                            if missing:
                                output_lines.append(f'      Note: Potentially missing fields: {missing}')
                        else:
                            output_lines.append(f"      ERROR: Expected a dictionary for a tool, but got {type(tool_data_dict)}")
                else:
                    output_lines.append(f"  ERROR: parser.parse() returned an unexpected type: {type(results)}")
            else:
                output_lines.append('  INFO: Parser did not recognize this page (can_parse returned False).')
        except Exception as e:
            output_lines.append(f"  CRITICAL ERROR during .can_parse() or .parse() for {fname}: {e}")
            import traceback
            import io
            buf = io.StringIO()
            traceback.print_exc(file=buf)
            output_lines.append(buf.getvalue())
            error_files_list.append(f"{fname} (Error in can_parse/parse: {e})")

        write_output(fname.replace('.html', '_output.txt'), '\n'.join(output_lines))

    print("\n--- Demo Script Finished ---")
    if error_files_list:
        print("\n--- Summary of Files with Errors/Issues ---")
        for error_entry in error_files_list:
            print(f"  - {error_entry}")

if __name__ == '__main__':
    print("=== About to call main() ===")
    main() 