%at least one node updates at each time
1{update(P,T,V):vertex(V)} :- exp(P,complete), time(P,T), time(P,T+1).

vlabel(P,T+1,V,1) :- update(P,T,V), 1{noneNegative(P,T,V,Id):functionOr(V,Id)}, vertex(V), exp(P,complete), not r_part(V), time(P,T+1).
vlabel(P,T+1,V,0) :- update(P,T,V), {noneNegative(P,T,V,Id):functionOr(V,Id)}0, vertex(V), exp(P,complete), functionOr(V,_), not r_gen(V), time(P,T+1).

%keep all others
vlabel(P,T+1,V,S) :- not update(P,T,V), vlabel(P,T,V,S), time(P,T+1), exp(P,complete).

#show update/3.

% show inconsistent nodes per exeperiment
inc(P,V) :- vlabel(P,T+1,V,0), 1{noneNegative(P,T,V,Id):functionOr(V,Id)}, vertex(V), exp(P,complete), r_part(V), time(P,T), time(P,T+1), update(P,T,V).
inc(P,V) :- vlabel(P,T+1,V,1), {noneNegative (P,T,V,Id):functionOr(V,Id)}0, vertex(V), exp(P,complete), functionOr(V,_), r_gen(V), time(P,T), time(P,T+1), update(P,T,V).
#show inc/2.
