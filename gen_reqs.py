_REQ_PATH = "./requirements.txt"
_WIN_REQ_PATH = "./winrequirements.txt"

with open(_REQ_PATH, "r") as file:
    reqs = [line.replace("\n", "").replace("\r", "") for line in sorted(file.readlines())]
    win_reqs = [line for line in reqs if not "uvloop" in line]


with open(_REQ_PATH, "w") as file:
    file.write("\n".join(reqs))
    print("UNIX requirements sorted in alphabetical order")


with open(_WIN_REQ_PATH, "w") as file:
    file.write("\n".join(win_reqs))
    print("Windows requirements generated and sorted in alphabetical order")
