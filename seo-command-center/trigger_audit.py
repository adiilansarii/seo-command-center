import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), "mcp"))
import server

export_dir = "../sample-export/"
print(f"Loading {export_dir}...")
server.seo_load(export_dir)

print("Detecting issues...")
server.seo_detect()

print("Generating fixes...")
server.seo_fix()

# Basic recommendations
issues = server.RUN["issues"]
recs = [f"Fix the {i['count']} {i['severity']}-severity '{i['type']}' issue(s)." for i in issues[:5]]
server.seo_recommend(recs)

print("Generating reports...")
server.seo_report()
server.seo_export()
print("Done!")
