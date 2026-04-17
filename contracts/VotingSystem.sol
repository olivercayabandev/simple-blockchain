// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract VotingSystem {
    string public name = "Barangay Voting System";
    string public symbol = "BVS";
    
    // Candidate struct
    struct Candidate {
        uint256 id;
        string name;
        string description;
        uint256 voteCount;
    }
    
    // Voter struct
    struct Voter {
        address walletAddress;
        string fullName;
        bool hasVoted;
        uint256 gasBalance;
    }
    
    // State variables
    mapping(uint256 => Candidate) public candidates;
    mapping(address => Voter) public voters;
    mapping(address => bool) public registeredVoters;
    address[] public voterAddresses;
    
    uint256 public candidateCount;
    uint256 public voterCount;
    bool public electionStarted;
    address public admin;
    
    // Events
    event CandidateAdded(uint256 indexed id, string name);
    event VoteCast(address indexed voter, uint256 indexed candidateId);
    event VoterRegistered(address indexed voter, string fullName);
    event ElectionStarted();
    event ElectionStopped();
    
    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin can call this");
        _;
    }
    
    constructor() {
        admin = msg.sender;
        electionStarted = false;
    }
    
    // Add a candidate (only admin)
    function addCandidate(string memory _name, string memory _description) public onlyAdmin {
        candidateCount++;
        candidates[candidateCount] = Candidate(candidateCount, _name, _description, 0);
        emit CandidateAdded(candidateCount, _name);
    }
    
    // Register a voter (only admin)
    function registerVoter(address _wallet, string memory _fullName) public onlyAdmin {
        require(!registeredVoters[_wallet], "Voter already registered");
        
        voters[_wallet] = Voter(_wallet, _fullName, false, 1 ether); // 1 ETH gas balance for simulation
        registeredVoters[_wallet] = true;
        voterAddresses.push(_wallet);
        voterCount++;
        
        emit VoterRegistered(_wallet, _fullName);
    }
    
    // Start election
    function startElection() public onlyAdmin {
        electionStarted = true;
        emit ElectionStarted();
    }
    
    // Stop election
    function stopElection() public onlyAdmin {
        electionStarted = false;
        emit ElectionStopped();
    }
    
    // Cast a vote
    function vote(uint256 _candidateId) public {
        require(electionStarted, "Election has not started");
        require(registeredVoters[msg.sender], "Not registered to vote");
        require(!voters[msg.sender].hasVoted, "Already voted");
        require(_candidateId > 0 && _candidateId <= candidateCount, "Invalid candidate");
        
        // Deduct simulated gas (0.001 ETH)
        require(voters[msg.sender].gasBalance >= 0.001 ether, "Insufficient gas");
        voters[msg.sender].gasBalance -= 0.001 ether;
        
        // Record vote
        voters[msg.sender].hasVoted = true;
        candidates[_candidateId].voteCount++;
        
        emit VoteCast(msg.sender, _candidateId);
    }
    
    // Get candidate details
    function getCandidate(uint256 _id) public view returns (uint256, string memory, string memory, uint256) {
        require(_id > 0 && _id <= candidateCount, "Invalid candidate");
        Candidate memory c = candidates[_id];
        return (c.id, c.name, c.description, c.voteCount);
    }
    
    // Get voter details
    function getVoter(address _wallet) public view returns (address, string memory, bool, uint256) {
        require(registeredVoters[_wallet], "Voter not registered");
        Voter memory v = voters[_wallet];
        return (v.walletAddress, v.fullName, v.hasVoted, v.gasBalance);
    }
    
    // Get all candidates count
    function getCandidateCount() public view returns (uint256) {
        return candidateCount;
    }
    
    // Check if address has voted
    function hasVoted(address _wallet) public view returns (bool) {
        return voters[_wallet].hasVoted;
    }
    
    // Get voting results
    function getResults() public view returns (uint256[] memory, string[] memory, uint256[] memory) {
        uint256[] memory ids = new uint256[](candidateCount);
        string[] memory names = new string[](candidateCount);
        uint256[] memory votes = new uint256[](candidateCount);
        
        for (uint256 i = 1; i <= candidateCount; i++) {
            ids[i-1] = i;
            names[i-1] = candidates[i].name;
            votes[i-1] = candidates[i].voteCount;
        }
        
        return (ids, names, votes);
    }
}
