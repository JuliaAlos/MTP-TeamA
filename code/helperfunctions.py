def read_file_and_return_positions(file_path):
    # Returns a DICTIONARY 
    # FORMAT
    # Number_of_line: line
    with open(file_path, 'r', newline='') as f:
        content = f.read()
    terms = content.split('\\r')
    terms = terms[:-1]
    values_dict = {}
    position = 0
    for term in terms:
        if term:
            values_dict[position] = term + "\\r"
        position +=  1
    return values_dict

def write_txt_file(file_path, content):
    with open(file_path, 'a', encoding='utf-8') as file:
        file.write(content)

def main():
    lines = read_file_and_return_positions("test.txt")

    for line in lines:
        write_txt_file("copy.txt", lines[line])

main()