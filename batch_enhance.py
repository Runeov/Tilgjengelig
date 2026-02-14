import os
import glob
import subprocess
import sys

def main():
    # Define the directory containing the reports
    reports_dir = os.path.join("reports", "counties")
    
    # Find all HTML files in the directory
    html_files = glob.glob(os.path.join(reports_dir, "*.html"))
    
    if not html_files:
        print(f"No HTML files found in {reports_dir}")
        return

    print(f"Found {len(html_files)} reports to upgrade.")
    
    # Counter for successful upgrades
    success_count = 0
    
    for filepath in html_files:
        print(f"Upgrading {filepath}...")
        try:
            # Run the upgrade_report.py script for each file
            # Using sys.executable ensures we use the same python interpreter
            result = subprocess.run(
                [sys.executable, "upgrade_report.py", filepath],
                capture_output=True,
                text=True,
                check=True
            )
            success_count += 1
            # print(result.stdout) # Optional: print stdout if needed
        except subprocess.CalledProcessError as e:
            print(f"Error upgrading {filepath}:")
            print(e.stderr)
        except Exception as e:
            print(f"Unexpected error on {filepath}: {e}")

    print("-" * 50)
    print(f"Batch upgrade complete.")
    print(f"Successfully upgraded: {success_count}/{len(html_files)}")

if __name__ == "__main__":
    main()
