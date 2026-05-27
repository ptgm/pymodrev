% assign final state time step
% obs_named_vlabel(Exp,Name,Node,Value) define the final state observed
% max_time(Exp, Time) defines the maximum time step

1{finalStateTime(P,T): T = 1..T2, max_time(P,T2)}1 :- obs_named_vlabel(P,final,_,_).
obs_vlabel(P,T,V,S) :- obs_named_vlabel(P,final,V,S), finalStateTime(P,T).

#minimize{T@3,finalState,P : finalStateTime(P,T)}.

%#show finalStateTime/2.

%obs_named_vlabel(xp1,final,v1,1).
%obs_named_vlabel(xp1,final,v3,1).
%obs_named_vlabel(xp1,final,v2,0).
%obs_named_vlabel(xp1,final,v4,0).
%max_time(xp1,5).
%obs_named_vlabel(xp2,final,v1,1).
%obs_named_vlabel(xp2,final,v3,1).
%obs_named_vlabel(xp2,final,v2,0).
%obs_named_vlabel(xp2,final,v4,0).
%max_time(xp2,10).
%#show obs_vlabel/4.
