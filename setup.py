import argparse
import tools.setup as tools_setup
import agents.setup as agents_setup

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools", action="store_true")
    parser.add_argument("--agents", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--reset", action="store_true", help="Passed through to agents setup")
    args = parser.parse_args()

    if args.tools or args.all or args.reset:
        tools_setup.main()
    
    if args.agents or args.all or args.reset:
        agents_setup.main(args.reset)

if __name__ == "__main__":
    main()