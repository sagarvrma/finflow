import boto3
import time

client = boto3.client('glue', region_name='us-east-1')

response = client.get_crawler(Name='finflow-market-data-crawler')
state = response['Crawler']['State']

if state == 'READY':
    client.start_crawler(Name='finflow-market-data-crawler')
    print("Crawler started.")
else:
    print(f"Crawler already in state: {state} — waiting.")

while True:
    state = client.get_crawler(Name='finflow-market-data-crawler')['Crawler']['State']
    if state == 'READY':
        break
    print(f"Crawler: {state}")
    time.sleep(10)

print("Crawler finished.")