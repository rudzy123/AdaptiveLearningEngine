---
title: Algorithms Primer (bundled fixture corpus)
license: MIT - original text written for this repository
---

## Big-O - Intuition
Big-O notation describes how the running time of an algorithm grows as the input size n grows, ignoring machine speed and small constants. It lets us compare algorithms by growth rate: an algorithm whose work is proportional to n scales gently, while one proportional to n^2 quickly becomes impractical as inputs get large.

## Big-O - Definition
We say f(n) is O(g(n)) if f(n) is bounded above by a constant multiple of g(n) for all sufficiently large n. In practice, drop constant factors and lower-order terms, keeping the fastest-growing term. Common classes from slow to fast growth are O(1), O(log n), O(n), O(n log n), and O(n^2). Loops that run one after another add their costs, while loops nested inside one another multiply them.

## Big-O - Worked example
Summing n numbers touches each number once, so the cost is O(n). The function f(n) = 4n^2 + 10n + 7 has dominant term 4n^2, so it is O(n^2). A loop over n items that does a constant 3 comparisons per item costs 3n, which is O(n). An outer loop of n steps with an inner loop of exactly 5 steps costs 5n, which is also O(n). Per-item cost multiplied by the number of items gives the total.

## Big-O - Common mistakes
Do not keep constants: O(3n^2) is just O(n^2). Do not keep lower-order terms: n^2 + n is O(n^2). Do not confuse sequential and nested loops: sequential loops add (n + n is O(n)), nested loops multiply (n times n is O(n^2)). Big-O describes growth, not the exact number of operations, so an O(n) algorithm can still be slower than an O(n^2) one on tiny inputs.

## Binary search - Intuition
Binary search finds a target in a sorted list by repeatedly halving the region where it could be, the way you look up a word in a dictionary by opening near the middle. Each comparison discards half of the remaining candidates, so even huge lists need only a handful of comparisons.

## Binary search - Definition
Keep two indices, lo and hi, bounding the search region. Compute mid = (lo + hi) // 2 using integer division and compare the list value at mid with the target. If they are equal, return mid. If the target is smaller, set hi = mid - 1; if larger, set lo = mid + 1. Stop when lo > hi, which means the target is absent. The list must be sorted, otherwise discarding half of it is not justified. Because each step halves the region, the running time is O(log n).

## Binary search - Worked example
Search the sorted list [4, 9, 15, 22, 31] for 22, with 0-indexed positions. Initially lo = 0 and hi = 4, so mid = 2 and the value there is 15. Since 22 is larger than 15, set lo = 3. Now mid = (3 + 4) // 2 = 3 and the value is 22, a match at index 3. Halving a list of 32 elements takes 5 steps (32, 16, 8, 4, 2, 1).

## Binary search - Common mistakes
Binary search only works on sorted data; on an unsorted list it can miss the target. Do not confuse the index of an element with its value: mid is an index into the list, and the value stored there is a different thing. The number of halvings is about log base 2 of n, not n divided by 2: a list of 1024 elements needs about 10 halving steps, not 512.

## Merge sort - Intuition
Merge sort is a divide-and-conquer algorithm. It splits the list in half, sorts each half the same way, and then merges the two sorted halves into one sorted list. A list of one element is already sorted, so the splitting stops there. The clever part is that merging two sorted lists is fast.

## Merge sort - Definition
Split the list into a left and right half recursively until each piece has one element. To merge two sorted lists, keep a pointer at the front of each, repeatedly take the smaller front element into the output, and advance that pointer, until both lists are used up. Merging costs time proportional to the total number of elements. A list of n elements is halved about log2 n times, giving log2 n levels, and each level does O(n) merging work, so the total running time is O(n log n) in the best, average, and worst cases.

## Merge sort - Worked example
Merge [2, 5, 9] and [1, 6, 7]. Compare the fronts 2 and 1 and take 1. Compare 2 and 6 and take 2. Compare 5 and 6 and take 5. Compare 9 and 6 and take 6. Compare 9 and 7 and take 7. The right list is exhausted, so append 9. The merged list is [1, 2, 5, 6, 7, 9]. For a list of 4 elements there are 2 levels of merging, and each level handles all 4 elements, for 8 units of work.

## Merge sort - Common mistakes
Concatenating two sorted lists does not produce a sorted list; the merge step must interleave elements by comparing fronts. Do not confuse the number of levels with the number of pieces: a list of 4 elements splits into 4 single-element pieces over 2 levels. Total work is levels times n (multiply), not levels plus n. Simple quadratic sorts have O(n^2) worst-case cost; the O(n log n) of merge sort is better.
