- First, we ensure the model width (often referred to as 𝑑model for isotropic architectures) is monotone in the hierarchy: 𝐷 0 ≤ 𝐷 1 ≤ · · · ≤ 𝐷𝑆 . This allows increasing compute and parameters used in the main network without significantly increasing its depth.
- Second, using efficient and powerful SSM layers in the outer networks allow reducing the number of layers used compared to similar prior architectures that only used Transformer layers (Slagle 2024); in this paper, we always stick to four layers (or the equivalent of four Mamba layers) in each encoder/decoder network.

To handle the changes in dimensions without an additional linear layer, we adopt the technique used in SpaceByte (Slagle 2024) with the marginal change: to expand dimensions (i.e., 𝐷𝑠 → 𝐷𝑠+1 ), we append all vectors with a shared trainable vector of dimension 𝐷𝑠+1 - 𝐷𝑠 ; to reduce dimensions (i.e., 𝐷𝑠+1 → 𝐷𝑠 ), we take the first 𝐷𝑠 dimensions from each vector.

We note that H-Net's performance can likely be improved with more careful tuning of the layer allocation and hyperparameters between sub-networks.

## 2.2 Dynamic Chunking (DC)

H-Net learns chunking boundaries through end-to-end training, allowing it to identify semantically meaningful units adaptively. Furthermore, this dynamic approach enables the model to allocate computational resources efficiently by compressing low-information regions while preserving high-information content at appropriate granularity.

## 2.2.1 Chunking Layer

The chunking layer (Chunk in equation (2)) contains a routing module and downsampler, as illustrated in Figure 1( bottom-right ).

Routing Module. In natural data, meaningful boundaries tend to emerge at points of contextual or semantic shift. From this observation, we add an inductive bias by measuring the similarity between adjacent representations: when context changes, consecutive vectors should exhibit lower similarity. The routing module implements this intuition through cosine similarity between adjacent encoder outputs. Given encoder outputs ˆ 𝑋, it calculates boundary probabilities 𝑝𝑡 and boundary indicators 𝑏𝑡 as follows:

<!-- formula-not-decoded -->

where 𝑝1 = 1.0 by definition, ensuring the sequence begins with a boundary. This formulation scales cosine similarity into a boundary score or probability: ideally, when consecutive vectors ˆ 𝑥𝑡 -1 and ˆ 𝑥𝑡 span a semantic boundary (e.g., between morphemes, words, or phrases), their projections 𝑞𝑡 and 𝑘𝑡 -1 diverge in the latent space, yielding low cosine similarity and consequently high boundary probability 𝑝𝑡 .

Downsampler. The downsampler compresses encoder outputs ˆ 𝑥 𝑠 into a reduced set of vectors 𝑥 𝑠+1 using boundary indicators {𝑏𝑠 𝑡 }𝐿𝑠 𝑡=1 . Among potential compression strategies - including mean pooling, max pooling, or cross-attention - we adopt direct selection of boundary-marked vectors for its simplicity and effectiveness (see Appendix E.1 for ablations).

As illustrated in Figure 1-(b), this approach follows a straightforward selection rule: vectors where 𝑏𝑡 = 1 are retained in the compressed sequence 𝑥 𝑠+1 , while those where 𝑏𝑡 = 0 are discarded. Likewise, the same downsampler applies to boundary probabilities, compressing 𝑝𝑠 into 𝑃 𝑠+1 for use in a dechunking layer (see Section 2.2.2).

## 2.2.2 Dechunking

The dechunking layer (Dechunk in equation (3)) consists of a smoothing module and upsampler, as illustrated in Figure 1( top-right ).

Smoothing Module. The critical challenge in training a dynamic chunking module lies in the discrete nature of chunk boundaries, which impedes gradient flow during backpropagation. We introduce the smoothing module as a technique to address this problem. As illustrated in Figure 1-(c), this component transforms discrete chunking operations into