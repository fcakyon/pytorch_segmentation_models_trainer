FROM pytorch/pytorch:latest
WORKDIR /code
COPY requirements.txt requirements.txt
RUN apt update \
    && apt install -y git htop nano libpq-dev python3-dev build-essential \
    && pip3 install -U debugpy jupyter flake8 pytest parameterized \
    && pip3 install torch-scatter -f https://pytorch-geometric.com/whl/torch-1.8.0+cu111.html \
    && pip3 install -r requirements.txt
COPY . .
RUN  pip3 install .
CMD ["jupyter", "notebook", "--notebook-dir=/github_repos", "--ip 0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]