import faiss
import numpy as np
from timeit import Timer
import matplotlib.pyplot as plt


number = 1000
TEST_NEIGHBOUR = True
TEST_VECTOR = False


def test_query(n_neighbour=10, indexer=None, dim=728):
    q = np.random.random((1, dim)).astype("float32")
    #print("query array {}".format(query_array.shape))
    D, I = indexer.search(q, n_neighbour)
    #print("D {}, I {}".format(D, I))


if __name__ == "__main__":
    if TEST_NEIGHBOUR:
        vectors = np.load("merged_paper_embedding.npy", allow_pickle=True).item()
        dim = len(vectors[next(iter(vectors))])
        print("vectors size {}, dim {}".format(len(vectors), dim))

        vectors_array = np.array(list(vectors.values()))

        index_l2 = faiss.IndexFlatL2(dim)
        index_l2.add(vectors_array)

        index_dot = faiss.IndexFlatIP(dim)
        index_dot.add(vectors_array)

        index_lsh = faiss.IndexLSH(dim, 24)
        index_lsh.add(vectors_array)

        index_lvh = faiss.IndexIVFPQ(index_lsh, dim, 100, 8, 8)

        x = np.arange(10, 1010, 100, dtype=int)
        l2_times = []
        dot_times = []
        lsh_times = []
        lvh_times = []
        for n_neighbour in x:
            n_neighbour = int(n_neighbour)
            l2_timer = Timer("test_query(n_neighbour, index_l2, dim)", "from __main__ import test_query, n_neighbour, index_l2, dim")
            l2_time = l2_timer.timeit(number)
            l2_times.append(l2_time)

            dot_timer = Timer("test_query(n_neighbour, index_dot, dim)", "from __main__ import test_query, n_neighbour, index_dot, dim")
            dot_time = dot_timer.timeit(number)
            dot_times.append(dot_time)

            lsh_timer = Timer("test_query(n_neighbour, index_lsh, dim)", "from __main__ import test_query, n_neighbour, index_lsh, dim")
            lsh_time = lsh_timer.timeit(number)
            lsh_times.append(lsh_time)

            lvh_timer = Timer("test_query(n_neighbour, index_lsh, dim)", "from __main__ import test_query, n_neighbour, index_lvh, dim")
            lvh_time = lvh_timer.timeit(number)
            lvh_times.append(lvh_time)

            print("n neighbour %d, iter number %d, l2 time %fs, dot time %fs, lsh time %fs" % (n_neighbour, number, l2_time, dot_time, lsh_time))

        ax = plt.subplot()
        ax.plot(x, l2_times, color="red", label="L2")
        ax.plot(x, dot_times, color="blue", label="Dot")
        ax.plot(x, lsh_times, color="black", label="LSH")
        ax.plot(x, lvh_times, color="green", label="LVH")
        ax.set_ylabel("Spend seconds")
        ax.set_xlabel("The number of neighbours")
        ax.legend()
        ax.set_title("Query Time Of L2, Dot, LSH, LVH")
        plt.savefig("neighbour.png")

    if TEST_VECTOR:
        l2_times = []
        dot_times = []
        lsh_times = []
        ivh_times = []
        dim = 128
        w = 10000
        sizes = np.arange(10*w, 110*w, 10*w)
        for sz in sizes:
            sz = int(sz)
            arr = np.random.random((sz, dim)).astype("float32")
            #print("arr shape {}".format(arr.shape))

            l2_indexer = faiss.IndexFlatL2(dim)
            l2_indexer.add(arr)
            l2_timer = Timer("test_query(100, l2_indexer, dim)", "from __main__ import test_query, sz, l2_indexer, dim")
            l2_time = l2_timer.timeit(number)
            l2_times.append(l2_time)

            dot_indexer = faiss.IndexFlatIP(dim)
            dot_indexer.add(arr)
            dot_timer = Timer("test_query(100, dot_indexer, dim)", "from __main__ import test_query, sz, dot_indexer, dim")
            dot_time = dot_timer.timeit(number)
            dot_times.append(dot_time)

            lsh_indexer = faiss.IndexLSH(dim, 64)
            lsh_indexer.add(arr)
            lsh_timer = Timer("test_query(100, lsh_indexer, dim)", "from __main__ import test_query, sz, lsh_indexer, dim")
            lsh_time = lsh_timer.timeit(number)
            lsh_times.append(lsh_time)

            ivh_indexer = faiss.IndexIVFFlat(l2_indexer, dim, 100)
            ivh_indexer.train(arr)
            ivh_indexer.add(arr)
            ivh_timer = Timer("test_query(100, ivh_indexer, dim)", "from __main__ import test_query, sz, ivh_indexer, dim")
            ivh_time = ivh_timer.timeit(number)
            ivh_times.append(ivh_time)

            del arr, l2_indexer, dot_indexer, lsh_indexer, ivh_indexer

            print("size {}, L2 {}s, dot {}s, LSH {}s, ivh {}s".format(sz, l2_time, dot_time, lsh_time, ivh_time))

        ax = plt.subplot()
        ax.plot(sizes, l2_times, color="red", label="L2")
        ax.plot(sizes, dot_times, color="blue", label="Dot")
        ax.plot(sizes, lsh_times, color="black", label="LSH")
        ax.plot(sizes, ivh_times, color="green", label="IVH")
        ax.set_ylabel("Spend seconds")
        ax.set_xlabel("Size")
        ax.legend()
        ax.set_title("Query Time Of L2, Dot, LSH, IVH different data size")
        plt.savefig("size.png")
