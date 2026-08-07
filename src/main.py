from bs4 import BeautifulSoup

with open("data/page.html", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

text = soup.get_text("\n", strip=True)

index = text.find("Понедельник")

print(text[index:index+3000])