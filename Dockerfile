FROM pytorch/pytorch:latest
COPY requirements.txt .
RUN apt update \
    && apt install -y git htop nano libpq-dev python3-dev build-essential \
    && pip install debugpy \
    && pip install torch-scatter -f https://pytorch-geometric.com/whl/torch-1.8.0+cu111.html \
    && pip3 install --no-cache-dir -r requirements.txt \
    && pip install -U jupyter git+https://github.com/phborba/pytorch_segmentation_models_trainer
CMD ["bash" "-c" "source /etc/bash.bashrc && jupyter notebook --notebook-dir=/github_repos --ip 0.0.0.0 --no-browser --allow-root"]