from global_constants import *
import numpy as np

def phone_distance(phone1, phone2):
    '''
    identical pairs --> 0
    unstressed / primary stress --> 1
    near-match consonants --> 2
    near-match vowels --> 4
    non-matched  --> np.inf
    '''
    if phone1 == phone2:
        return 0
    elif filter(str.isalpha, phone1) == filter(str.isalpha, phone2):
        # small penalty if identical BUT one has a primary stress and the other is nonstressed
        if (phone1[-1], phone2[-1]) == ('0','1') or (phone1[-1], phone2[-1]) == ('1','0'):
            return 1
        # no penalty for secondary stress discrepancies
        else:
            return 0
    elif (phone1,phone2) in NEAR_MISS_CONSONANTS or (phone2,phone1) in NEAR_MISS_CONSONANTS:
        return 2
    # make sure to strip off the (possibly nonexistent) before checking for set inclusion
    # if the vowels don't match then the stresses DEFINITELY need to match
    # TODO: handle this via some sort of custom lookup function
    elif ((phone1[:-1],phone2[:-1]) in NEAR_MISS_VOWELS or (phone2[:-1],phone1[:-1]) in NEAR_MISS_VOWELS) and phone1[-1] == phone2[-1]:
        return 4
    else:
        return np.inf

def phoneme_distance(phoneme1, phoneme2):
    '''
    Don't use fancy hand-coded rules, keep the same distance logic, just swap in the new metric
    '''
    return sum([phone_distance(str(p1),str(p2)) for (p1,p2) in zip(phoneme1, phoneme2)])

class PortmanteauInclusive(object):
	# Should set these using the *global* constants
	min_overlap_vowel_phones = 1
	min_overlap_consonant_phones = 1
	max_overlap_dist = 3 # 4 is too lenient, needed something more aggressive

	# Want to only consider start of word, or want to also do middle of word?
	# Try *all* internal matches, so reason to restrict ourselves
	
	def __init__(self,
							word_short,
							word_long,
							grapheme_portmanteau,
							arpabet_portmanteau,
							reconstruction_proba,
							n_overlapping_vowel_phones,
							n_overlapping_consonant_phones,
							n_overlapping_phones,
							overlap_distance,
							overlap_grapheme_phoneme_prob):
		self.word_short = word_short
		self.word_long = word_long
		self.grapheme_portmanteau = grapheme_portmanteau
		self.arpabet_portmanteau = arpabet_portmanteau
		self.reconstruction_proba = reconstruction_proba	
		self.n_overlapping_vowel_phones = n_overlapping_vowel_phones
		self.n_overlapping_consonant_phones = n_overlapping_consonant_phones
		self.n_overlapping_phones = n_overlapping_phones
		self.overlap_distance = overlap_distance
		self.overlap_grapheme_phoneme_prob = overlap_grapheme_phoneme_prob

	@classmethod
	def get_portmanteau_inclusive(cls, word1, word2, pronunciation_dictionary):
		'''
		Attempts to create a Portmanteau out of the two words
		If successful, returns the Portmanteau
		If unnsuccessful, returns nil along with a descriptive error message

		We need the 'pronunciation_dictionary' in order to determine the probability of each grapheme
		'''

		# these are the default return values if no good overlaps are found
		portmanteau, status, message = None, 1, 'no <=max_overlap_dist overlaps were found'

		if len(word1.arpabet_phoneme) == len(word2.arpabet_phoneme):
			portmanteau, status, message = None, 1, 'arpabet phonemes are same length, can\'t construct inclusion'
			return portmanteau, status, message # terminate immediately
		elif len(word1.arpabet_phoneme) < len(word2.arpabet_phoneme):
			word_short, word_long = word1, word2
		else:
			word_short, word_long = word2, word1

		# Every overlap will contain all of word_short, so check that its vowels/consonants/length are sufficient
		num_overlap_vowel_phones = sum([1 if filter(str.isalpha, str(phone)) in ARPABET_VOWELS else 0 for phone in word_short.arpabet_phoneme])
		num_overlap_consonant_phones = sum([1 if filter(str.isalpha, str(phone)) in ARPABET_CONSONANTS else 0 for phone in word_short.arpabet_phoneme])

		if num_overlap_vowel_phones < cls.min_overlap_vowel_phones:
			portmanteau, status, message = None, 1, 'arpabet overlap does not have enough vowels'
			return portmanteau, status, message # terminate immediately
		elif num_overlap_consonant_phones < cls.min_overlap_consonant_phones:
			portmanteau, status, message = None, 1, 'arpabet overlap does not have enough consonants'
			return portmanteau, status, message # terminate immediately

		for arpabet_start_idx in range(len(word_long.arpabet_phoneme) - len(word_short.arpabet_phoneme) + 1):
			# word1_idx = len(word1.arpabet_phoneme) - overlap_len
			# word2_idx = overlap_len
			word_short_arpabet_overlap = word_short.arpabet_phoneme
			word_long_arpabet_overlap = word_long.arpabet_phoneme[arpabet_start_idx:arpabet_start_idx+len(word_short.arpabet_phoneme)]
			# need to split into preceding and following
			word_long_arpabet_nonoverlap1 = word_long.arpabet_phoneme[:arpabet_start_idx]
			word_long_arpabet_nonoverlap2 = word_long.arpabet_phoneme[arpabet_start_idx+len(word_short.arpabet_phoneme):]
			overlap_distance = phoneme_distance(word_short_arpabet_overlap, word_long_arpabet_overlap)
			if overlap_distance <= cls.max_overlap_dist:
				# scrap the vectorizable phoneme mapping step, operate solely on the arpabet phoneme
					
				try:
					word_long_grapheme_overlap_start_idx, word_long_grapheme_overlap_end_idx = word_long.grapheme_to_arpabet_phoneme_alignment.subseq2_inds_to_subseq1_inds(arpabet_start_idx, arpabet_start_idx + len(word_short.arpabet_phoneme) - 1)
				except:
					portmanteau, status, message = None, 1, 'arpabet_phoneme could not be aligned with grapheme'
					continue

				if word_long.grapheme[word_long_grapheme_overlap_start_idx:word_long_grapheme_overlap_end_idx+1] == word_short.grapheme:
					portmanteau, status, message = None, 1, 'grapheme overlaps are identical'
					continue

				# All alignments and min-char requirements have been met, so create the Portmanteau, and return

				# pick the graphemetric representation such that the constituent words are most easily reconstruble
				# i.e. use the innards of the word which is most easily predicted from its dangling phones

				# handle edge-case where word_short is at the HEAD of word_long
				if arpabet_start_idx == 0:
					word_long_grapheme_nonoverlap1 = ''
				else:
					word_long_grapheme_nonoverlap1 = ''.join(word_long.grapheme_to_arpabet_phoneme_alignment.subseq2_to_subseq1(0, arpabet_start_idx-1))

				# handle edge-case where word_short is at the TAIL of word_long
				if arpabet_start_idx + len(word_short.arpabet_phoneme) == len(word_long.arpabet_phoneme):
					word_long_grapheme_nonoverlap2 = ''
				else:
					word_long_grapheme_nonoverlap2 = ''.join(word_long.grapheme_to_arpabet_phoneme_alignment.subseq2_to_subseq1(arpabet_start_idx + len(word_short.arpabet_phoneme), len(word_long.arpabet_phoneme) - 1))

				word_long_prob_given_nonoverlap_graphs1 = cls.get_prob_word_given_subgrapheme(word_long_grapheme_nonoverlap1, 'head', pronunciation_dictionary)
				word_long_prob_given_nonoverlap_graphs2 = cls.get_prob_word_given_subgrapheme(word_long_grapheme_nonoverlap2, 'tail', pronunciation_dictionary)
				word_long_prob_given_nonoverlap_graphs = max(word_long_prob_given_nonoverlap_graphs1, word_long_prob_given_nonoverlap_graphs2)

				grapheme_portmanteau = word_long_grapheme_nonoverlap1 + word_short.grapheme + word_long_grapheme_nonoverlap2
				arpabet_portmanteau = word_long_arpabet_nonoverlap1 + word_short.arpabet_phoneme + word_long_arpabet_nonoverlap2

				# probability of a phoneme occurring with a particular occompanying grapheme is inversely proportional to the pun's quality; same is true for rhymes
				# basically, this is a roundabout way of identifying/discarding common prefixes/suffixes (commonly occurring graph/phone combinations at the start/end of words)
				word_short_overlap_grapheme_phoneme_prob = cls.get_grapheme_phoneme_prob(word_short.grapheme, word_short.arpabet_phoneme, pronunciation_dictionary)
				word_long_overlap_grapheme_phoneme_prob = cls.get_grapheme_phoneme_prob(word_long.grapheme[word_long_grapheme_overlap_start_idx:word_long_grapheme_overlap_end_idx+1], word_long_arpabet_overlap, pronunciation_dictionary)
				overlap_grapheme_phoneme_prob = max(word_short_overlap_grapheme_phoneme_prob, word_long_overlap_grapheme_phoneme_prob)

				portmanteau = cls(
					word_short,
					word_long,
					grapheme_portmanteau,
					arpabet_portmanteau,
					word_long_prob_given_nonoverlap_graphs,
					num_overlap_vowel_phones,
					num_overlap_consonant_phones,
					num_overlap_vowel_phones+num_overlap_consonant_phones,
					overlap_distance,
					overlap_grapheme_phoneme_prob
					)
				return portmanteau, 0, 'portmanteau found!'

		# failed to find any overlaps meeting the 'max_overlap_dist' criteria, so return with default error message
		return portmanteau, status, message

	@staticmethod
	def get_prob_word_given_subgrapheme(subgrapheme, side, pronunciation_dictionary):
		'''
		Given that we know a grapheme contains a certain substring at a certain position, what is the probability that we can guess the grapheme?

		Need to have access to the PronounciationDictionary... how to do it?

		This _may_ be prohibitively innefficient to run every time... not sure

		Should be called with *dangling* grapheme substring

		As always, indices are inclusive, so add 1 to end_idx

		side = 'head' or 'tail'
		'''
		if side == 'head':
			subgraph_matches = [1 if subgrapheme == grapheme[:len(subgrapheme)] else 0 for grapheme in pronunciation_dictionary.grapheme_to_word_dict.iterkeys()]
		elif side == 'tail':
			# need to explicitly add 'len(grapheme)' to the negative-indexing to handle 0-cases
			subgraph_matches = [1 if subgrapheme == grapheme[len(grapheme)-len(subgrapheme):] else 0 for grapheme in pronunciation_dictionary.grapheme_to_word_dict.iterkeys()]
		else:
			raise "Argument 'side' must be either 'head' or 'tail'"
		
		return 1.0 / sum(subgraph_matches)

	@staticmethod
	def get_grapheme_phoneme_prob(subgrapheme, subphoneme, pronunciation_dictionary):
		'''
		How common is it for this particular graphic+phonetic element to occur at the start of end of a word?
		If it's extremely common, then it's probably a (garbage) common prefix/suffix
		'''
		subgrapheme_matches_head = np.array([1 if subgrapheme == grapheme[:len(subgrapheme)] else 0 for grapheme in pronunciation_dictionary.grapheme_to_word_dict.iterkeys()])
		# need to explicitly add 'len(grapheme)' to the negative-indexing to handle 0-cases
		subgrapheme_matches_tail = np.array([1 if subgrapheme == grapheme[len(grapheme)-len(subgrapheme):] else 0 for grapheme in pronunciation_dictionary.grapheme_to_word_dict.iterkeys()])
		subphoneme_matches_head = np.array([1 if subphoneme == word.arpabet_phoneme[:len(subphoneme)] else 0 for word in pronunciation_dictionary.grapheme_to_word_dict.itervalues()])
		# need to explicitly add 'len(word.arpabet_phoneme)' to the negative-indexing to handle 0-cases
		subphoneme_matches_tail = np.array([1 if subphoneme == word.arpabet_phoneme[len(word.arpabet_phoneme)-len(subphoneme):] else 0 for word in pronunciation_dictionary.grapheme_to_word_dict.itervalues()])
		return 1.0 * ((subgrapheme_matches_head & subphoneme_matches_head) | (subgrapheme_matches_tail & subphoneme_matches_tail)).sum() / len(pronunciation_dictionary.grapheme_to_word_dict)

	def __repr__(self):
		return '''
		-------------------------------------------------------------------------------
		# Word Combination: {} + {}
		# Grapheme Portmanteau: {}
		# Phoneme Portmanteau: {}
		# Phoneme Distance: {}
		# Grapheme+Phoneme Probability: {}
		# Overlapping Phones: {}
		# Overlapping Vowel Phones: {}
		# Overlapping Consonant Phones: {}
		-------------------------------------------------------------------------------
		'''.format(self.word_short.grapheme,
			self.word_long.grapheme,
			self.grapheme_portmanteau,
			'-'.join(self.arpabet_portmanteau), # represented internally as a list, so collapse the list to a string
			self.overlap_distance,
			round(self.overlap_grapheme_phoneme_prob, 5),
			self.n_overlapping_phones,
			self.n_overlapping_vowel_phones,
			self.n_overlapping_consonant_phones)

	def __str__(self):
		return '{} ({}/{})'.format(self.grapheme_portmanteau, self.word_short.grapheme, self.word_long.grapheme)

	def ordering_criterion(self):
		'''Smaller values are "better" portmanteaus'''
		return (-self.n_overlapping_phones, self.overlap_distance, self.overlap_grapheme_phoneme_prob)
		# return (-self.n_overlapping_phones, self.overlap_grapheme_phoneme_prob)
		# return (self.overlap_grapheme_phoneme_prob, -self.n_overlapping_phones, -self.n_overlapping_vowel_phones, self.overlap_distance)