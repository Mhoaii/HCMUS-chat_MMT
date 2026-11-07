from .app import main
import argparse

parser = argparse.ArgumentParser(description="Giao diện LAN Chat")
parser.add_argument("--demo", action="store_true", help="Chỉ dùng dữ liệu mẫu, không mở mạng")
main(demo=parser.parse_args().demo)
