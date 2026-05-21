import boto3
import subprocess
import json
import datetime

# ─── CONFIGURATION ────────────────────────
# REPLACE THESE WITH YOUR VALUES:
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:NetworkAlerts"
S3_BUCKET     = "netguard-logs-yourname-2024"
REGION        = "us-east-1"

# Hosts to monitor
# Add any IP addresses you want to watch
HOSTS = {
    "Google DNS"     : "8.8.8.8",
    "Cloudflare DNS" : "1.1.1.1",
    "Amazon DNS"     : "8.8.4.4",
}
# ──────────────────────────────────────────

sns = boto3.client("sns", region_name=REGION)
s3  = boto3.client("s3",  region_name=REGION)
cw  = boto3.client("cloudwatch", region_name=REGION)

def ping(ip):
    """Returns True if host is reachable"""
    result = subprocess.run(
        ["ping", "-c", "3", "-W", "3", ip],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return result.returncode == 0

def send_alert(name, ip):
    """Send email alert via SNS"""
    sns.publish(
        TopicArn = SNS_TOPIC_ARN,
        Subject  = f"ALERT: {name} is DOWN",
        Message  = f"""
Network Monitor Alert
─────────────────────
Host    : {name}
IP      : {ip}
Status  : UNREACHABLE
Time    : {datetime.datetime.utcnow()} UTC

Please investigate immediately.
        """
    )
    print(f"  📧 Alert sent for {name}")

def push_metric(name, is_up):
    """Push availability metric to CloudWatch"""
    cw.put_metric_data(
        Namespace  = "NetGuard",
        MetricData = [{
            "MetricName" : "HostAvailability",
            "Dimensions" : [{"Name": "Host", "Value": name}],
            "Value"      : 1 if is_up else 0,
            "Unit"       : "Count",
            "Timestamp"  : datetime.datetime.utcnow()
        }]
    )

def save_log(data):
    """Save results to S3"""
    key = f"logs/{datetime.datetime.utcnow().strftime('%Y/%m/%d/%H-%M-%S')}.json"
    s3.put_object(
        Bucket      = S3_BUCKET,
        Key         = key,
        Body        = json.dumps(data, indent=2),
        ContentType = "application/json"
    )
    print(f"  💾 Log saved → s3://{S3_BUCKET}/{key}")

def run():
    print(f"\n{'='*45}")
    print(f"  NetGuard Monitor — {datetime.datetime.utcnow().strftime('%H:%M:%S')} UTC")
    print(f"{'='*45}")

    results = []

    for name, ip in HOSTS.items():
        is_up  = ping(ip)
        status = "UP ✅" if is_up else "DOWN ❌"
        print(f"  {status}  {name} ({ip})")

        # Push to CloudWatch
        push_metric(name, is_up)

        # Send alert if down
        if not is_up:
            send_alert(name, ip)

        results.append({
            "host"   : name,
            "ip"     : ip,
            "status" : "UP" if is_up else "DOWN",
            "time"   : datetime.datetime.utcnow().isoformat()
        })

    # Save to S3
    save_log({
        "summary" : "ALL UP" if all(r["status"]=="UP" for r in results) else "ISSUES FOUND",
        "results" : results
    })

    print(f"{'='*45}\n")

if __name__ == "__main__":
    run()
