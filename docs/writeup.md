# Half of what my store sells has never sold before
I own a small Funko Pop store. When a new release comes in, I buy six to twelve pieces,
they sell, and the next release replaces them. That purchasing model has a consequence I
did not appreciate until I tried to build a recommender on my own order history: 61% of
the variants I have ever sold appear in exactly one order, and in the test window, 45% of
the items a customer actually added to a basket had never sold before that window began.

Every recommender that reasons about item identities is blind to that 45%. This post is
about what that did to the design, and the one result that went the opposite way from
what I predicted.

## The protocol came first

The question is basket completion: given what is in front of a customer, rank the rest
of the catalog. User-based methods were ruled out by the data, not by preference, since
13% of customers ever return and most in-store orders carry no customer at all.

Before writing a model I wrote the protocol into the README: a time-based split with
train through March 2026, validation on April and May, and test from June onward;
leave-one-out queries over multi-item baskets; Hit@10 as the selection metric; a
1,000-draw cluster bootstrap over baskets for intervals; hyperparameters chosen on
validation only and test scored once. The store's existing co-purchase analysis, at its
production support threshold, is reported as-is whatever validation preferred, because
that is the number the models have to beat.

That floor turned out to be low. The production setting has something to say on 7% of
queries and lands the hidden item in its top ten 0.3% of the time. It was built to show
a human recurring bundles, and it does that. It is not a recommender.

## The number

On 606 test queries, every model keyed on item identity scores exactly 0.0% on cold
targets. Not low. Zero. An item that never sold in the fitting window cannot be ranked
by its id, so it sits in a tie block thousands wide.

A content model with no basket data at all, just "resembles what is in the basket" over
tags, title keywords, and a price band, takes the cold segment from 0.0% to 10.9%, and is
the best single model overall at 7.8% Hit@10. The validated hybrid of content, item
similarity, and attribute co-occurrence reaches 11.9% [8.3%, 15.7%], more than double the
best baseline at 5.3% and 11.6 points over production, with a confidence interval that
clears both.

The features that carry it are not the ones I expected either. Rarity is barely tagged
in my catalog, with fourteen items tagged Chase, but it is in titles at scale: over a
thousand titles say "exclusive", hundreds say "vault" or "chase". So the feature builder
parses titles rather than trusting tags.

## The failure

The design predicted that a learned attribute model would be the primary one: pointwise
mutual information between attributes, learned from every multi-item basket, capturing
"people who buy this franchise also buy that one." It lost to plain cosine similarity on
the item's own features, 3.5% against 7.8%.

On 1,400 baskets, PMI between hundreds of attributes is mostly noise around the one
signal that matters, which is "same franchise, same price band," and cosine captures that
directly. The learned model still earns a weight in the blend, so it adds something the
others lack. It is just not the model the design said it would be, and the README says
so rather than dropping the row.

Validation also ran hot. The hybrid scored 19.8% on April and May and 11.9% on test. That
gap is reported, not tuned away, because the only way to close it would be to look at
test more than once.

## What the evaluation cannot see

The offline evaluation knows when an item existed. It does not know whether it was on
the shelf. With six-unit buys that sell through in anywhere from a week to never, a model
can be scored wrong for recommending something that sold out that morning, and there is
no stock history to correct for it.

So stock is a serving rule, never a feature. The container pulls live inventory every
fifteen minutes and applies it as a hard filter by default. The first time I ran it
against the real store, only 40% of the catalog was in stock, and all five unfiltered
top suggestions for a Batman Pop were sold out. The evaluation would never have told me
that.

## Keeping the numbers honest

Three mechanics do most of the work. Ties are scored at their expected rank under random
tie-breaking, so a popularity model that gives thousands of items the same score is
neither flattered nor punished. Every table carries an "answered" column, because a
model that abstains on most queries can post inflated coverage and novelty on the few it
answers. And CI re-runs the whole evaluation from the committed public snapshot on every
push and fails if a fresh point estimate differs from the committed one by more than
one part in a billion, so a number in the README cannot drift away from the code that
produced it.

The same container serves a dashboard a store owner can leave open: Pop numbers as the
visual signature, because that is how staff talk about stock, and a why-bar on every
suggestion saying whether it rests on "bought together," "looks alike," or "goes with
this kind."

## What I would tell someone starting this

Look at your purchasing model before your model. If your catalog turns over faster than
it accumulates evidence, the item is the wrong unit to learn on and content is the
primary path, not the fallback. Write the protocol before the model. Report the row that
embarrasses you. And put the thing in front of live stock before believing any number,
because the metric cannot see the shelf.

Repo: github.com/peterzemore/basket-recommender
