import argparse
from model import *
from utils import *
import os
import time
from torch.utils.data import DataLoader
import torch.optim as optim

os.environ["CUDA_VISIBLE_DEVICES"] = "2"

parser = argparse.ArgumentParser()
parser.add_argument('--embedding_size', type=int, default=300)
parser.add_argument('--batch_size', type=int, default=128)
parser.add_argument('--n_epoch', type=int, default=10)
parser.add_argument('--n_class', type=int, default=3)
parser.add_argument('--n_layers', type=int, default=5)
parser.add_argument('--aspect_kinds', type=int, default=5)
parser.add_argument('--pre_processed', type=bool, default=True)
parser.add_argument('--learning_rate', type=float, default=0.001)
parser.add_argument('--l2_reg', type=float, default=0)
parser.add_argument('--clip', type=float, default=3.0)
parser.add_argument('--dropout', type=float, default=0.2)
parser.add_argument('--max_aspect_len', type=int, default=0)
parser.add_argument('--max_sentence_len', type=int, default=0)
parser.add_argument('--dataset', default='data/restaurant/')
parser.add_argument('--embedding_file_name', default='data/glove.840B.300d.txt')
parser.add_argument('--embedding', default=0)
parser.add_argument('--vocab_size', type=int, default=0)

config = parser.parse_args()

def main():
    start_time = time.time()
    print('Loading data info ...')
    word2id, config.max_aspect_len, config.max_sentence_len = get_data_info(config.dataset, config.pre_processed)
    config.vocab_size = len(word2id)
    train_data = read_data(word2id, config.max_aspect_len, config.max_sentence_len, config.dataset + 'train',
                           config.pre_processed)
    test_data = read_data(word2id, config.max_aspect_len, config.max_sentence_len, config.dataset + 'test',
                          config.pre_processed)
    print('Loading pre-trained word vectors ...')
    config.embedding = load_word_embeddings(config.embedding_file_name, config.embedding_size, word2id)
    train_dataset = GCAEDataset(train_data)
    test_dataset = GCAEDataset(test_data)
    train_loader = DataLoader(dataset=train_dataset, batch_size=config.batch_size, shuffle=True, num_workers=2)
    test_loader = DataLoader(dataset=test_dataset, batch_size=config.batch_size, shuffle=True, num_workers=2)
    embedding = nn.Embedding(config.vocab_size, config.embedding_size)
    embedding.weight.data.copy_(torch.from_numpy(config.embedding))
    model = GCAE(
        embedding=embedding,
        kernel_num=100,
        kernel_sizes=[3, 4, 5],
        aspect_embedding=embedding,
        aspect_kernel_num=100,
        aspect_kernel_sizes=[3],
        dropout=config.dropout
    )
    model = model.cuda()
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=config.learning_rate, weight_decay=config.l2_reg)
    max_acc = 0
    for epoch in range(config.n_epoch):
        train_total_cases = 0
        train_correct_cases = 0
        for data in train_loader:
            aspects, sentences, labels, _, _, _ = data
            aspects, sentences, labels = aspects.cuda(), sentences.cuda(), labels.cuda()
            optimizer.zero_grad()
            outputs = model(sentences, aspects)
            _, predicts = outputs.max(dim=1)
            train_total_cases += labels.shape[0]
            train_correct_cases += (predicts == labels).sum().item()
            loss = criterion(outputs, labels)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), config.clip)
            optimizer.step()
        train_accuracy = train_correct_cases / train_total_cases
        test_total_cases = 0
        test_correct_cases = 0
        for data in test_loader:
            aspects, sentences, labels, _, _, _ = data
            aspects, sentences, labels = aspects.cuda(), sentences.cuda(), labels.cuda()
            outputs = model(sentences, aspects)
            _, predicts = outputs.max(dim=1)
            test_total_cases += labels.shape[0]
            test_correct_cases += (predicts == labels).sum().item()
        test_accuracy = test_correct_cases / test_total_cases
        print('[epoch %03d] train accuracy: %.4f test accuracy: %.4f' % (epoch, train_accuracy, test_accuracy))
        max_acc = max(max_acc, test_accuracy)
    print('max test accuracy: %.4f' % max_acc)
    end_time = time.time()
    print('Time Costing: %s' % (end_time - start_time))

if __name__ == '__main__':
    main()