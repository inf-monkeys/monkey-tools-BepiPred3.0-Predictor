# Monkey Tool BepiPred3.0-Predictor

This is a monkey tool wrapper of [https://github.com/UberClifford/BepiPred3.0-Predictor].

## Configuration

Create a `config.yaml` in the source code folder:

```yaml
port: 5000

s3:
  endpoint: ''
  accessKeyId: ''
  secretAccessKey: ''
  region: ''
  bucket: ''
  publicAccessUrl: ''
```

## Quick Start

### 🧑‍💻 Developer

1. Clone the repo
   ```sh
   git clone https://github.com/inf-monkeys/monkey-tools-BepiPred3.0-Predictor.git
   ```

2. Go to `monkey-tools-BepiPred3.0-Predictor` folder

   ```sh
   cd monkey-tools-BepiPred3.0-Predictor
   ```

3. Install python dependencies:

    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

4. Start the API Server:

    ```bash
    python app.py
    ```

### 🐳 Docker

1. Build Docker Image

    ```sh
    docker build . -t infmonkeys/monkey-tools-bepipred3.0-predictor -f Dockerfile-cpu
    ```

2. Run Docker Container

    ```sh
    docker run -v ./config.yaml:/app/config.yaml -p 5000:5000  --name monkey-tools-bepipred3.0-predictor -d docker.io/library/monkey-tools-bepipred3.0-predictor
    ```
