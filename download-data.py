import os
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

URL = "https://svs.gsfc.nasa.gov/vis/a020000/a020200/a020255/frames/3840x2160_16x9_60p/Shot48/Shot48Frames/"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")

# Resolve Desktop path
desktop = os.path.join(os.path.expanduser("~"), "Desktop")
output_dir = os.path.join(desktop, "knob-data-sets")
os.makedirs(output_dir, exist_ok=True)

class ImageLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for attr, value in attrs:
                if attr == "href" and value.lower().endswith(IMAGE_EXTENSIONS):
                    self.links.append(value)

# Download the directory HTML
with urllib.request.urlopen(URL) as response:
    html = response.read().decode("utf-8")

# Parse image links
parser = ImageLinkParser()
parser.feed(html)

print(f"Found {len(parser.links)} images.")

# Download images
for link in parser.links:
    image_url = urljoin(URL, link)
    filename = os.path.basename(urlparse(image_url).path)
    output_path = os.path.join(output_dir, filename)

    if os.path.exists(output_path):
        print(f"Skipping existing file: {filename}")
        continue

    print(f"Downloading {filename}...")
    urllib.request.urlretrieve(image_url, output_path)

print("Done ✅")
