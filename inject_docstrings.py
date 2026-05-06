import os
import re
import glob

def process_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        match = re.match(r'^def (test_([a-zA-Z0-9_]+))\((.*)\):', line)
        if match:
            test_name = match.group(1)
            
            # Remove existing docstring if present
            next_i = i + 1
            if next_i < len(lines) and lines[next_i].strip().startswith('"""'):
                # find the end of the docstring
                if lines[next_i].strip() == '"""':
                    # one line docstring, but wait, usually """ doc """
                    pass
                if lines[next_i].strip().count('"""') == 2:
                    i = next_i
                else:
                    j = next_i + 1
                    while j < len(lines) and '"""' not in lines[j]:
                        j += 1
                    i = j
            
            # parse US and AC
            us_num = "US-UNKNOWN"
            ac_num = "AC-UNKNOWN"
            tc_id = "000"
            
            # extract e.g. test_ac_001_1
            ac_match = re.search(r'test_ac_(\d+)(_(\d+))?', test_name)
            if ac_match:
                us_id = ac_match.group(1)
                sub_id = ac_match.group(3) if ac_match.group(3) else "1"
                us_num = f"US-{us_id}"
                ac_num = f"AC-{us_id}-{sub_id}"
                tc_id = f"{us_id}{sub_id}"
            
            indent_match = re.match(r'^(\s*)', lines[i+1] if i+1 < len(lines) else "    ")
            indent = "    "
            
            docstring = f'''{indent}"""
{indent}[@{ac_num},{us_num}]
{indent}TC-Unit-{tc_id}:
{indent}  @[Name]: {test_name}
{indent}  @[Priority]: P1 Functional
{indent}  @[Category]: Typical
{indent}  @[Purpose]: Verify {test_name}
{indent}  @[Brief]: Systematically tests the {test_name} behavior.
{indent}  @[Expect]: Test passes and adheres to conditions.
{indent}"""
'''
            new_lines.append(docstring)
        i += 1
        
    with open(filepath, 'w') as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    test_files = glob.glob("tests/*.py")
    for f in test_files:
        if not f.endswith("conftest.py"):
            process_file(f)
