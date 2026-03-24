import sys
import re

def normalize_logic_expression(expression):
    """
    Takes a raw logic string like: "(B && A) || (D && !C)"
    Returns a sorted canonical form: (('!C', 'D'), ('A', 'B'))
    """
    # 1. Split by OR (||)
    clauses = expression.split('||')
    
    canonical_clauses = []
    
    for clause in clauses:
        # 2. Clean up: Remove parentheses and whitespace
        clean_clause = clause.replace('(', '').replace(')', '').strip()
        if not clean_clause:
            continue
            
        # 3. Split by AND (&&) to get the variables
        variables = [v.strip() for v in clean_clause.split('&&')]
        
        # 4. Sort variables alphabetically
        canonical_clauses.append(tuple(sorted(variables)))
    
    # 5. Sort the clauses themselves
    return tuple(sorted(canonical_clauses))

def parse_op(node, op_str):
    """
    Parses an operation string like 'F,(A && !B) || (C)' or 'E,A,B'
    Returns a canonical tuple.
    """
    if ',' not in op_str:
        return (node, op_str)
    
    parts = op_str.split(',', 1)
    op_type = parts[0].strip()
    rest = parts[1].strip()
    
    if op_type == 'F':
        canonical_expr = normalize_logic_expression(rest)
        return ('F', node, canonical_expr)
    else:
        # For E, A, R: treat the rest as a simple comma-separated tuple
        return (op_type, node, tuple(v.strip() for v in rest.split(',')))

def parse_file(filepath):
    """
    Parses a pymodrev output file into a set of repair sets.
    Each repair set is represented as a frozenset of operations.
    """
    try:
        with open(filepath, 'r') as f:
            content = f.read().strip()
    except FileNotFoundError:
        return set()

    if not content:
        return set()
    
    if 'Consistent!' in content:
        return {'Consistent!'}

    # Remove the "Inconsistent!" header if present
    content = content.replace('Inconsistent!', '').strip()

    # Split by the main separator '/' between nodes
    raw_chunks = content.split('/')
    parsed_data = set()
    for chunk in raw_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        if '@' in chunk:
            node, rest = chunk.split('@', 1)
            # Different repair sets for the same node are separated by ';'
            repair_sets = rest.split(';')
            for rs_str in repair_sets:
                if not rs_str.strip():
                    continue
                # Individual operations within a repair set are separated by ':'
                ops = rs_str.split(':')
                canonical_rs = []
                for op in ops:
                    if not op.strip():
                        continue
                    canonical_rs.append(parse_op(node, op.strip()))
                # Store as frozenset to make it hashable and order-independent
                parsed_data.add(frozenset(canonical_rs))
        else:
            # Fallback for cases like simple node lists
            parsed_data.add(frozenset([(chunk,)]))
            
    return parsed_data

def main():
    if len(sys.argv) != 3:
        print(f'Usage: python {sys.argv[0]} <pymodrev_output1> <pymodrev_output2>')
        sys.exit(1)
    file1 = sys.argv[-2]
    file2 = sys.argv[-1]

    try:
        # Parse both files into sets of repair sets
        data1 = parse_file(file1)
        data2 = parse_file(file2)

        if data1 != data2:
            # Calculate differences
            only_in_1 = data1 - data2
            only_in_2 = data2 - data1
            
            if only_in_1:
                print(f"  Only in {file1}:")
                for rs in sorted(list(only_in_1), key=str):
                    # Pretty print the frozenset
                    print(f"    {sorted(list(rs), key=str)}")
                    
            if only_in_2:
                print(f"  Only in {file2}:")
                for rs in sorted(list(only_in_2), key=str):
                    print(f"    {sorted(list(rs), key=str)}")

    except FileNotFoundError as e:
        print(f"Error: File not found - {e.filename}")
    except Exception as e:
        print(f"Error processing files: {e}")

if __name__ == "__main__":
    main()
