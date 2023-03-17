### 环境依赖

OCR技术支持: https://github.com/alisen39/TrWebOCR

#### Docker部署

```bash
docker pull mmmz/trwebocr:latest

docker run -itd --rm -p 8089:8089 --name trwebocr mmmz/trwebocr:latest 
```