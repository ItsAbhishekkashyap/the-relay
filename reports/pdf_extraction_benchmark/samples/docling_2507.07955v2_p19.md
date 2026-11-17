Figure 9: SpaceByte++ encoder-decoder architecture ablation using raw byte inputs. We evaluate four encoderdecoder (E 0 - D 0 ) configurations: M4-M4 , M2T1-T1M2 and T1M2-M2T1, and T2-T2, where M denotes Mamba layers and T denotes Transformer layers.

<!-- image -->

Figure 10: Encoder-decoder architecture ablation using BPE-tokenized inputs. Assuming that GPT-2 tokenizer serves as the outermost encoder-decoder (i.e., E 0 -D 0 ), we evaluate six E 1 -D 1 combinations: M6-M6, M4T1-T1M4, T1M4-M4T1, M2T2-T2M2, T2M2-M2T2, and T3-T3.

<!-- image -->

layer and T denotes a Transformer layer. These combinations are chosen by keeping the symmetry and replacing each Transformer layer with two Mamba-2 layers, as they contain equivalent parameter counts - 12𝐷 2 for Transformer (4𝐷 2 for the attention mechanism and 8𝐷 2 for an MLP) vs. ≈ 6𝐷 2 per Mamba-2 layer (no MLP).

Figure 8 and Figure 9 demonstrate that Mamba layers are essential for effective byte-level sequence processing. For both H-Net and SpaceByte++, the pure Transformer configuration (T2-T2) exhibits by far the worst performance despite using more FLOPs (it also down-compresses sequences poorly compared to other configurations, thus using more compute in the main network). This configuration struggles to compress byte sequences effectively, resulting in both computational waste and degraded modeling performance. Performance improves monotonically with increased Mamba layer allocation, achieving optimal results with the highest compression efficiency in the pure Mamba configuration (M4-M4). These findings align with recent research demonstrating SSMs' advantages over Transformers for fine-grained sequence modeling (Goel et al. 2022; Schiff et al. 2024), as corroborated by MambaByte's superior performance over LlamaByte in Figure 3.

A natural question arises: does the importance of Mamba layers (i) stem specifically from processing fine-grained byte inputs, or (ii) because they are better for compressing information into the next stage, even at coarser input resolutions? To investigate these hypotheses, we train a 1-stage H-Net on top of BPE-tokenized inputs processed by the GPT-2 tokenizer. We then evaluate six different encoder-decoder combinations.

- If hypothesis (i) holds, then we would expect different combinations of Mamba/Transformer layers in the encoder/decoder to have similar performance, since it is known that they have similar performance on standard tokenized language modeling.
- If hypothesis (ii) holds, then we would expect that encoders/decoders using some Mamba layers to be better than pure Transformer layers.

As demonstrated in Figure 10, Mamba layers prove significantly important even when processing BPE tokens rather than raw bytes, providing evidence for the second hypothesis.

We hypothesize that this consistent advantage across input granularities stems from fundamental architectural differences between SSMs and Transformers. While Transformers naturally store complete key-value caches for all positions, SSMs are designed to compress information into fixed-size states. This compression-oriented architecture aligns naturally with our chunking mechanism, which requires aggregating multiple input vectors into consolidated representations. The inherent compression capability of Mamba layers makes them particularly well-suited for the encoder and decoder roles in our hierarchical architecture (Gu 2025). Based on these findings, we employ Mamba layers throughout all encoders and decoders in our final H-Net configuration, as detailed in Table 1.