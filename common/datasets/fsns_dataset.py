from collections import defaultdict

import numpy as np

from imgaug import augmenters as iaa
from imgaug import parameters as iap

from common.datasets.text_recognition_image_dataset import TextRecognitionImageDataset


class FSNSDataset(TextRecognitionImageDataset):

    def __init__(self, *args, **kwargs):
        kwargs['resize_after_load'] = False
        self.jump_to_max_level = kwargs.pop('jump_to_max_level', False)
        super().__init__(*args, **kwargs)
        self.word_lengths = self.get_length_index_map()

        self.level = min(self.word_lengths.keys())
        if self.jump_to_max_level:
            self.level = max(self.word_lengths.keys())

    def level_up(self):
        self.level = min(self.level + 1, len(self.word_lengths))

    def __len__(self):
        return len(self.word_lengths[self.level])

    @property
    def num_chars_per_word(self):
        return self.num_chars

    @property
    def num_words_per_image(self):
        return self.num_words

    def get_word(self, i):
        return self.get_gt_item('text', i)

    def get_length_index_map(self):
        # returns a dict that maps word lengths to their corresponding ids
        lengths = defaultdict(list)
        for i in range(super().__len__()):
            line = self.get_word(i)
            word_length = 0
            for word_length, word in enumerate(line):
                if all([char == self.char_map[str(self.blank_label)] for char in word]):
                    break
            lengths[word_length].append(i)
        return dict(lengths)

    def get_words(self, i):
        words = self.get_word(i)
        label_words = []
        for word in words:
            labels = [np.array([int(self.reverse_char_map[character])], dtype=self.label_dtype) for character in word]
            labels += [np.full_like(labels[0], self.blank_label)] * (self.num_chars_per_word - len(labels))
            label_words.append(np.concatenate(labels, axis=0))

        label_words += [np.full_like(label_words[0], self.blank_label)] * (self.num_words_per_image - len(label_words))
        label_words = np.stack(label_words, axis=0)
        only_blank_labels = (label_words == self.blank_label).all(axis=1)
        num_words = -1
        for i in range(len(only_blank_labels)):
            if only_blank_labels[i]:
                num_words = i
                break

        return label_words, np.full((4,), num_words, dtype=self.label_dtype)

    def init_augmentations(self):
        if self.transform_probability > 0 and self.use_imgaug:
            augmentations = iaa.Sometimes(
                self.transform_probability,
                iaa.Sequential([
                    iaa.SomeOf(
                        (1, None),
                        [
                            iaa.AddToHueAndSaturation(iap.Uniform(-20, 20), per_channel=True),
                            iaa.LinearContrast((0.75, 1.0)),
                        ],
                        random_order=True
                    )
                ])
            )
        else:
            augmentations = None
        return augmentations

    def get_gt_index(self, index):
        assert index <= len(self), f"Index {index} in FSNS dataset is larger than it should be. Should be max. {len(self)}"
        base_index = 0
        for level in range(min(self.word_lengths.keys()), self.level + 1):
            if base_index + len(self.word_lengths[level]) > index:
                return self.word_lengths[level][index - base_index]

    def get_example(self, i):
        i = self.get_gt_index(i)
        return super().get_example(i)